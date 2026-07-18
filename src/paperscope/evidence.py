"""Bounded, deterministic evidence-bundle generation for the (future) calibration pipeline.

Unlike `statistics.py`, this reads full review text, so it only runs against the
full-text corpus tier (`data/full/<family>.jsonl`) -- never the excerpted public tier
(`data/public/<family>.jsonl`), which has already discarded the text this module needs.
`is_public_tier` refuses the latter with a clear error rather than silently degrading.

Every excerpt keeps full provenance (evidence ID, venue/year, forum ID, note ID, source
URL, initial/final rating designation, decision, content hash, excerpt length, corpus
hash) so a bundle stays independently checkable without its source corpus -- see
`validate_evidence_bundle`.

Selection is stratified across five axes (decision, rating tercile, year, reviewer
disagreement, rebuttal presence) and seeded for reproducibility: the same seed against
the same corpus always produces the same bundle; a different seed generally produces a
different one, *except* when every stratum is small enough that `--per-bucket` never
oversubscribes it -- in that degenerate case sampling has nothing to choose between, and
the bundle is seed-invariant by construction, not a bug.

The final size cap (`--max-items`) is a bound only, not a rebalancing step: if the
pre-cap stratified selection is downsampled to fit, the post-cap bundle is no longer
guaranteed to represent every stratum evenly.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from paperscope.config import (
    DEFAULT_EVIDENCE_MAX_ITEMS,
    DEFAULT_EVIDENCE_PER_BUCKET,
    EVIDENCE_EXCERPT_MAX_CHARS,
    EVIDENCE_SCHEMA_VERSION,
)
from paperscope.models import ForumRecord, Review, content_hash
from paperscope.storage import atomic_write_text

AXES: tuple[str, ...] = ("decision_bucket", "rating_bucket", "year", "disagreement_bucket", "rebuttal_bucket")

_REQUIRED_STR_FIELDS = (
    "evidence_id", "venue_family", "forum_id", "note_id", "source_url",
    "rating_designation", "decision", "content_hash", "corpus_hash",
)


class EvidenceValidationError(ValueError):
    """Raised with every violation found in a bundle, one per line -- not just the first."""


@dataclass
class EvidenceItem:
    evidence_id: str
    venue_family: str
    venue_year: int | str
    forum_id: str
    note_id: str
    source_url: str
    rating_designation: str  # "initial" | "final"
    rating_value: float | None
    decision: str  # normalized decision text; "" is stored as "unknown"
    content_hash: str  # the source Review.content_hash -- full text, pre-truncation
    excerpt_text: str  # truncated to EVIDENCE_EXCERPT_MAX_CHARS
    excerpt_length: int  # len() of the full, untruncated excerpt-source text
    corpus_hash: str
    schema_version: int = EVIDENCE_SCHEMA_VERSION
    strata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def evidence_id_for(forum_id: str, note_id: str, rating_designation: str) -> str:
    """Deterministic, seed-independent: the same review always gets the same ID,
    regardless of which seed's sampling run happens to select it.
    """
    return "ev_" + content_hash(forum_id, note_id, rating_designation)


def is_public_tier(records: dict[str, ForumRecord]) -> bool:
    """True if this corpus was loaded from the excerpted public tier.

    `storage._excerpt()` unconditionally replaces `review.text` with a
    `{excerpt, length, hash}` dict on the public tier -- even for originally-empty
    text -- so checking the *type* of the first review's `text` field found is a
    fully reliable tier discriminator: always `str` (full tier) or always `dict`
    (public tier), never mixed within one corpus.
    """
    for record in records.values():
        for review in record.reviews:
            return isinstance(review.text, dict)
    return False


def _excerpt_source_text(review: Review) -> str:
    if review.text:
        return review.text
    combined = f"{review.strengths} {review.weaknesses}".strip()
    if combined:
        return combined
    return review.summary


def _designated_rating(review: Review) -> tuple[str, float | None]:
    if review.final_rating is not None and review.final_rating.value is not None:
        return "final", review.final_rating.value
    return "initial", review.initial_rating.value


def _decision_bucket(normalized: str) -> str:
    if normalized == "accept":
        return "accepted"
    if normalized in ("reject", "desk_reject"):
        return "rejected"
    return "unknown"


def _tercile_bucket(value: float | None, lo_cut: float, hi_cut: float) -> str:
    if value is None:
        return "unknown"
    if value < lo_cut:
        return "low"
    if value > hi_cut:
        return "high"
    return "medium"


@dataclass
class _Candidate:
    record: ForumRecord
    review: Review
    excerpt_source: str
    rating_designation: str
    rating_value: float | None
    strata: dict[str, str]

    @property
    def sort_key(self) -> tuple[str, str]:
        return self.record.forum_id, self.review.note_id or ""


def _build_candidates(
    records: dict[str, ForumRecord], held_out_forum_ids: set[str] | None
) -> list[_Candidate]:
    held_out_forum_ids = held_out_forum_ids or set()

    # rating terciles are computed once, globally, over every candidate's designated
    # rating value -- see module docstring; ties lean toward the "medium" bucket.
    prelim: list[tuple[ForumRecord, Review, str, str, float | None]] = []
    for forum_id in sorted(records):
        record = records[forum_id]
        if forum_id in held_out_forum_ids:
            continue
        for review in sorted(record.reviews, key=lambda r: r.note_id or ""):
            source = _excerpt_source_text(review)
            if not source:
                continue
            designation, value = _designated_rating(review)
            prelim.append((record, review, source, designation, value))

    rating_values = sorted(v for _r, _rv, _s, _d, v in prelim if v is not None)
    if rating_values:
        lo_cut = rating_values[len(rating_values) // 3]
        hi_cut = rating_values[(2 * len(rating_values)) // 3]
    else:
        lo_cut = hi_cut = 0.0

    # disagreement median split: per-forum range (max-min) over rated reviews with >=2
    # ratings; forums below that threshold get "insufficient_data" on this axis only.
    forum_ranges: dict[str, float] = {}
    for forum_id, record in records.items():
        vals = [r.initial_rating.value for r in record.reviews if r.initial_rating.value is not None]
        if len(vals) >= 2:
            forum_ranges[forum_id] = max(vals) - min(vals)
    sorted_ranges = sorted(forum_ranges.values())
    if sorted_ranges:
        n = len(sorted_ranges)
        median_range = (
            sorted_ranges[n // 2]
            if n % 2
            else (sorted_ranges[n // 2 - 1] + sorted_ranges[n // 2]) / 2
        )
    else:
        median_range = 0.0

    candidates = []
    for record, review, source, designation, value in prelim:
        decision_bucket = _decision_bucket(record.decision.normalized or "")
        rating_bucket = _tercile_bucket(value, lo_cut, hi_cut)
        year = record.venue_year if record.venue_year is not None else "unspecified"
        if record.forum_id in forum_ranges:
            disagreement_bucket = "high" if forum_ranges[record.forum_id] > median_range else "low"
        else:
            disagreement_bucket = "insufficient_data"
        rebuttal_bucket = "present" if record.responses else "absent"
        candidates.append(
            _Candidate(
                record=record,
                review=review,
                excerpt_source=source,
                rating_designation=designation,
                rating_value=value,
                strata={
                    "decision_bucket": decision_bucket,
                    "rating_bucket": rating_bucket,
                    "year": str(year),
                    "disagreement_bucket": disagreement_bucket,
                    "rebuttal_bucket": rebuttal_bucket,
                },
            )
        )
    return candidates


def _to_item(candidate: _Candidate, *, corpus_hash: str) -> EvidenceItem:
    record, review = candidate.record, candidate.review
    year = record.venue_year if record.venue_year is not None else "unspecified"
    excerpt_text = candidate.excerpt_source[:EVIDENCE_EXCERPT_MAX_CHARS]
    return EvidenceItem(
        evidence_id=evidence_id_for(record.forum_id, review.note_id or "", candidate.rating_designation),
        venue_family=record.venue_family,
        venue_year=year,
        forum_id=record.forum_id,
        note_id=review.note_id or "",
        source_url=record.url,
        rating_designation=candidate.rating_designation,
        rating_value=candidate.rating_value,
        decision=record.decision.normalized or "unknown",
        content_hash=review.content_hash,
        excerpt_text=excerpt_text,
        excerpt_length=len(candidate.excerpt_source),
        corpus_hash=corpus_hash,
        strata=dict(candidate.strata),
    )


def select_evidence(
    records: dict[str, ForumRecord],
    *,
    seed: int,
    corpus_hash: str,
    max_items: int = DEFAULT_EVIDENCE_MAX_ITEMS,
    per_bucket: int = DEFAULT_EVIDENCE_PER_BUCKET,
    held_out_forum_ids: set[str] | None = None,
) -> list[EvidenceItem]:
    if is_public_tier(records):
        raise ValueError(
            "evidence generation requires the full-text corpus tier "
            "(data/full/<family>.jsonl); got a public/excerpted corpus"
        )
    if max_items < 0 or per_bucket < 0:
        raise ValueError("max_items and per_bucket must be non-negative")

    candidates = _build_candidates(records, held_out_forum_ids)
    rng = random.Random(seed)

    selected: dict[str, EvidenceItem] = {}
    if per_bucket > 0:
        for axis in AXES:
            categories = sorted({c.strata[axis] for c in candidates})
            for category in categories:
                pool = sorted(
                    (c for c in candidates if c.strata[axis] == category), key=lambda c: c.sort_key
                )
                k = min(per_bucket, len(pool))
                if k == 0:
                    continue
                for chosen in rng.sample(pool, k):
                    item = _to_item(chosen, corpus_hash=corpus_hash)
                    selected.setdefault(item.evidence_id, item)

    if len(selected) > max_items:
        keep_ids = set(rng.sample(sorted(selected), max_items))
        selected = {eid: item for eid, item in selected.items() if eid in keep_ids}

    return sorted(selected.values(), key=lambda it: (it.venue_family, str(it.venue_year), it.forum_id, it.note_id))


def validate_evidence_bundle(
    items: list[EvidenceItem],
    records: dict[str, ForumRecord],
    *,
    held_out_forum_ids: set[str] | None = None,
) -> None:
    """Raises EvidenceValidationError listing every violation found, or returns None."""
    held_out_forum_ids = held_out_forum_ids or set()
    errors: list[str] = []
    seen_ids: set[str] = set()

    for item in items:
        label = item.evidence_id or "<missing evidence_id>"

        for field_name in _REQUIRED_STR_FIELDS:
            if not getattr(item, field_name, None):
                errors.append(f"{label}: missing provenance field '{field_name}'")
        if item.venue_year in (None, ""):
            errors.append(f"{label}: missing provenance field 'venue_year'")

        if item.evidence_id in seen_ids:
            errors.append(f"duplicate evidence_id: {item.evidence_id}")
        seen_ids.add(item.evidence_id)

        record = records.get(item.forum_id)
        if record is None:
            errors.append(f"{label}: unknown forum_id {item.forum_id!r}")
            continue

        review = next((r for r in record.reviews if r.note_id == item.note_id), None)
        if review is None:
            errors.append(f"{label}: unknown note_id {item.note_id!r} in forum {item.forum_id!r}")
            continue

        if item.content_hash != review.content_hash:
            errors.append(f"{label}: content hash does not match source review")
        else:
            source_text = _excerpt_source_text(review)
            if not source_text.startswith(item.excerpt_text):
                errors.append(f"{label}: excerpt text is not a prefix of the current source review")

        if record.venue_family != item.venue_family or (
            (record.venue_year if record.venue_year is not None else "unspecified") != item.venue_year
        ):
            errors.append(
                f"{label}: unsupported venue/year claim "
                f"({item.venue_family}/{item.venue_year} vs actual {record.venue_family}/{record.venue_year})"
            )

        if item.forum_id in held_out_forum_ids:
            errors.append(f"{label}: forum {item.forum_id!r} overlaps the held-out evaluation set")

    if errors:
        raise EvidenceValidationError("; ".join(errors))


def write_evidence_bundle(
    path: Path, items: list[EvidenceItem], *, corpus_hash: str, generated_at: str, seed: int
) -> dict:
    payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "corpus_hash": corpus_hash,
        "generated_at": generated_at,
        "seed": seed,
        "count": len(items),
        "items": [i.to_dict() for i in items],
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))
    return payload
