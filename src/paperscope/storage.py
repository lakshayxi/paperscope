"""Two-tier corpus storage.

Tier 1, "full" -- complete review/rebuttal text, kept purely local (gitignored, never
committed anywhere, including the `data` branch). Used for local evidence-bundle and
generation work in a later phase.

Tier 2, "public index" -- the same paper-centric records, but review/response text is
replaced with a bounded short excerpt + a content hash + length. This is what the CI
workflow commits to the `data` branch. Numeric/structural fields (ratings, confidence,
decision, IDs, URLs, timestamps) are kept in full since they're data points, not prose
being redistributed. See docs/redistribution.md for the reasoning behind this split.

JSONL for per-record data, a separate manifest.json for dataset-level metadata. Writes
are atomic (write to a temp file, then os.replace) so a crash mid-write never corrupts
the existing corpus.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

from paperscope import __version__ as PAPERSCOPE_VERSION
from paperscope.config import PUBLIC_EXCERPT_MAX_CHARS, SCHEMA_VERSION, VENUE_GROUPS
from paperscope.models import ForumRecord, Rating, Review
from paperscope.sampling import VenueCursor


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text)
    tmp.replace(path)


def full_corpus_path(venue_family: str, base_dir: Path = Path("data/full")) -> Path:
    return base_dir / f"{venue_family}.jsonl"


def public_index_path(venue_family: str, base_dir: Path = Path("data/public")) -> Path:
    return base_dir / f"{venue_family}.jsonl"


def manifest_path(venue_family: str, base_dir: Path = Path("data/public")) -> Path:
    return base_dir / f"{venue_family}.manifest.json"


def cursor_state_path(venue_family: str, base_dir: Path = Path("data/full")) -> Path:
    return base_dir / f"{venue_family}.cursors.json"


def load_cursor_state(path: Path) -> dict[str, VenueCursor]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {venue_id: VenueCursor.from_dict(c) for venue_id, c in raw.items()}


def save_cursor_state(path: Path, cursors: dict[str, VenueCursor]) -> None:
    raw = {venue_id: c.to_dict() for venue_id, c in cursors.items()}
    atomic_write_text(path, json.dumps(raw, indent=2, sort_keys=True))


def load_corpus(path: Path) -> dict[str, ForumRecord]:
    """Load a JSONL corpus (full or public tier) keyed by forum_id."""
    if not path.exists():
        return {}
    records: dict[str, ForumRecord] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        record = ForumRecord.from_dict(d)
        records[record.forum_id] = record
    return records


def save_full_corpus(path: Path, records: dict[str, ForumRecord]) -> None:
    lines = [json.dumps(r.to_dict(), sort_keys=True) for r in records.values()]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def _excerpt(text: str, max_chars: int) -> dict:
    text = text or ""
    return {
        "excerpt": text[:max_chars],
        "length": len(text),
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    }


def to_public_dict(record: ForumRecord, excerpt_max_chars: int = PUBLIC_EXCERPT_MAX_CHARS) -> dict:
    """Strip full review/response text down to a short excerpt + hash + length, for
    anything committed publicly. Numeric/structural fields pass through unchanged.
    """
    d = record.to_dict()
    for review in d.get("reviews", []):
        for field in ("text", "strengths", "weaknesses", "questions", "summary"):
            review[field] = _excerpt(review.get(field, ""), excerpt_max_chars)
    for response in d.get("responses", []):
        response["text"] = _excerpt(response.get("text", ""), excerpt_max_chars)
    return d


def save_public_index(
    path: Path, records: dict[str, ForumRecord], excerpt_max_chars: int = PUBLIC_EXCERPT_MAX_CHARS
) -> None:
    lines = [json.dumps(to_public_dict(r, excerpt_max_chars), sort_keys=True) for r in records.values()]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def corpus_hash(records: dict[str, ForumRecord]) -> str:
    """Deterministic hash over all forum IDs + review note IDs, for integrity/change
    detection without needing to hash full text.
    """
    h = hashlib.sha256()
    for forum_id in sorted(records):
        h.update(forum_id.encode("utf-8"))
        for review in sorted(r.note_id or "" for r in records[forum_id].reviews):
            h.update(review.encode("utf-8"))
    return h.hexdigest()[:16]


def write_manifest(
    path: Path,
    *,
    venue_family: str,
    records: dict[str, ForumRecord],
    seed: int | None,
    generated_at: float | None = None,
) -> dict:
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "paperscope_version": PAPERSCOPE_VERSION,
        "venue_family": venue_family,
        "generated_at": generated_at if generated_at is not None else time.time(),
        "record_count": len(records),
        "review_count": sum(len(r.reviews) for r in records.values()),
        "seed": seed,
        "corpus_hash": corpus_hash(records),
    }
    atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _venue_family_for_display_name(display_name: str) -> str:
    for family, names in VENUE_GROUPS.items():
        if display_name in names:
            return family
    return "unknown"


def migrate_legacy_corpus(legacy_path: Path) -> dict[str, dict[str, ForumRecord]]:
    """Import an old flat corpus_<family>.json (one row per review, no paper/decision
    metadata, keyed by display name like "ICLR 2024") into the new paper-centric schema,
    grouped by the venue family it belongs to.

    Best-effort: the legacy format has no paper title/abstract/decision alongside bulk
    reviews, so migrated records carry only what's derivable -- forum_id, review note ids
    and text, ratings -- with paper/decision left empty and explicitly unknown, not
    invented. Preserves forum/note IDs so evidence tracing still works for migrated data.
    """
    if not legacy_path.exists():
        raise FileNotFoundError(legacy_path)
    legacy = json.loads(legacy_path.read_text())

    by_family: dict[str, dict[str, ForumRecord]] = {}
    for display_name, reviews in legacy.items():
        if display_name.startswith("_forum_") or not isinstance(reviews, list):
            continue
        family = _venue_family_for_display_name(display_name)
        year_match = re.search(r"\d{4}", display_name)
        year = int(year_match.group()) if year_match else None
        family_records = by_family.setdefault(family, {})

        for r in reviews:
            forum_id = r.get("forum_id")
            if not forum_id:
                continue
            record = family_records.get(forum_id)
            if record is None:
                record = ForumRecord(
                    forum_id=forum_id,
                    url=f"https://openreview.net/forum?id={forum_id}",
                    venue_family=family,
                    venue_id=display_name,
                    venue_year=year,
                    api_version="unknown",
                    sampling_method="migrated_legacy",
                )
                family_records[forum_id] = record
            _append_migrated_review(record, r)
    return by_family


def _append_migrated_review(record: ForumRecord, legacy_review: dict) -> None:
    note_id = legacy_review.get("note_id")
    if note_id and any(rv.note_id == note_id for rv in record.reviews):
        return  # already migrated
    rating_num = legacy_review.get("rating_num")
    review = Review(
        note_id=note_id,
        initial_rating=Rating(raw=str(legacy_review.get("rating", "")), value=rating_num),
        confidence=Rating(raw=str(legacy_review.get("confidence", ""))),
        summary=legacy_review.get("summary", "") or "",
        text=legacy_review.get("text", "") or "",
        strengths=legacy_review.get("strengths", "") or "",
        weaknesses=legacy_review.get("weaknesses", "") or "",
        questions=legacy_review.get("questions", "") or "",
    )
    review.content_hash = review.compute_hash()
    record.reviews.append(review)
