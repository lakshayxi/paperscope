"""paperscope CLI -- Phase 1 scope: fetch venue, fetch forum, migrate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from paperscope import evidence as evidence_mod
from paperscope import refresh_policy as refresh_policy_mod
from paperscope import statistics as statistics_mod
from paperscope import storage
from paperscope.config import (
    ARTIFACTS_DIR,
    DEFAULT_EVIDENCE_MAX_ITEMS,
    DEFAULT_EVIDENCE_PER_BUCKET,
    DEFAULT_PER_VENUE,
    DEFAULT_SEED,
    VENUES,
)
from paperscope.discovery import discover_review_invitation
from paperscope.openreview_client import auth_mode, get_client
from paperscope.parsing import build_forum_record
from paperscope.sampling import VenueCursor, fetch_unseen_submissions


def _year_of(display_name: str) -> int | None:
    m = re.search(r"\d{4}", display_name)
    return int(m.group()) if m else None


def _venue_entries(families: list[str] | None, years: list[int] | None):
    for display_name, venue_id, api_version, family in VENUES:
        if families and family not in families:
            continue
        if years and display_name != "TMLR" and _year_of(display_name) not in years:
            continue
        yield display_name, venue_id, api_version, family


def _refresh_forum(client, record) -> tuple[object | None, bool]:
    """Re-fetch one forum's children; return (fresh_record_or_None, changed)."""
    try:
        paper_note = client.get_note(record.forum_id)
        children = client.get_notes(forum=record.forum_id)
    except Exception:
        return None, False
    fresh = build_forum_record(
        paper_note,
        children,
        venue_family=record.venue_family,
        venue_id=record.venue_id,
        venue_year=record.venue_year,
        api_version=record.api_version,
        sampling_method="refresh",
        sampling_seed=record.sampling_seed,
    )
    old_hashes = sorted(r.content_hash for r in record.reviews)
    new_hashes = sorted(r.content_hash for r in fresh.reviews)
    changed = old_hashes != new_hashes or record.decision.raw_text != fresh.decision.raw_text
    return fresh, changed


def cmd_fetch_venue(args) -> None:
    families = [f.lower() for f in args.family] if args.family else None
    years = [int(y) for y in args.years] if args.years else None
    if not families:
        sys.exit("--family is required, e.g. --family iclr")

    overall_summary = []
    for family in families:
        full_path = storage.full_corpus_path(family)
        public_path = storage.public_index_path(family)
        manifest_p = storage.manifest_path(family)
        cursor_p = storage.cursor_state_path(family)

        full_records = storage.load_corpus(full_path)
        cursors = storage.load_cursor_state(cursor_p)

        for display_name, venue_id, api_version, _fam in _venue_entries([family], years):
            client = get_client(api_version)
            venue_year = _year_of(display_name)
            seen_ids = {fid for fid, r in full_records.items() if r.venue_id == venue_id}
            cursor = cursors.setdefault(venue_id, VenueCursor())

            new_notes, cursor = fetch_unseen_submissions(
                client, venue_id, api_version, args.papers, cursor, seen_ids, args.seed
            )
            cursors[venue_id] = cursor

            new_count, error_count = 0, 0
            for note in new_notes:
                try:
                    children = client.get_notes(forum=note.id)
                    record = build_forum_record(
                        note, children,
                        venue_family=family, venue_id=venue_id, venue_year=venue_year,
                        api_version=api_version, sampling_method="acquisition", sampling_seed=args.seed,
                    )
                    refresh_policy_mod.apply_refresh_result(record, fetched_ok=True, changed=True)
                    full_records[record.forum_id] = record
                    new_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"  [{display_name}] fetch error for a submission: {e}", flush=True)

            refreshed_count = 0
            if args.refresh_policy != "none":
                venue_records = [r for r in full_records.values() if r.venue_id == venue_id]
                candidates = refresh_policy_mod.select_candidates(
                    venue_records, refresh_policy=args.refresh_policy, expiry_days=args.refresh_expiry_days
                )
                for record, _reason in candidates[: args.refresh_limit]:
                    fresh, changed = _refresh_forum(client, record)
                    if fresh is None:
                        refresh_policy_mod.apply_refresh_result(
                            record, fetched_ok=False, changed=False,
                            max_attempts=args.refresh_max_attempts, expiry_days=args.refresh_expiry_days,
                        )
                        continue
                    fresh.refresh = record.refresh
                    refresh_policy_mod.apply_refresh_result(
                        fresh, fetched_ok=True, changed=changed,
                        max_attempts=args.refresh_max_attempts, expiry_days=args.refresh_expiry_days,
                    )
                    full_records[fresh.forum_id] = fresh
                    refreshed_count += 1

            status = "partial" if error_count > 0 else "ok"
            overall_summary.append({
                "venue": display_name, "status": status,
                "new": new_count, "refreshed": refreshed_count, "errors": error_count,
            })
            print(f"  [{display_name}] +{new_count} new, {refreshed_count} refreshed, {error_count} errors", flush=True)

        storage.save_full_corpus(full_path, full_records)
        storage.save_public_index(public_path, full_records)
        storage.write_manifest(manifest_p, venue_family=family, records=full_records, seed=args.seed)
        storage.save_cursor_state(cursor_p, cursors)

    print("BULK_SUMMARY_JSON=" + json.dumps(overall_summary))
    if not overall_summary:
        sys.exit(f"no venues matched family={families} years={years}")
    if any(s["status"] == "partial" for s in overall_summary):
        sys.exit(1)


def cmd_fetch_forum(args) -> None:
    forum_id = args.url
    if forum_id.startswith("http"):
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(forum_id).query)
        forum_id = qs.get("id", [forum_id])[0]

    client = get_client("v2")
    try:
        paper_note = client.get_note(forum_id)
        api_version = "v2"
    except Exception:
        client = get_client("v1")
        paper_note = client.get_note(forum_id)
        api_version = "v1"

    children = client.get_notes(forum=forum_id)
    record = build_forum_record(
        paper_note, children,
        venue_family="unknown", venue_id="unknown", venue_year=None, api_version=api_version,
    )
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))


def cmd_migrate(args) -> None:
    by_family = storage.migrate_legacy_corpus(Path(args.legacy_corpus))
    for family, records in by_family.items():
        full_path = storage.full_corpus_path(family)
        existing = storage.load_corpus(full_path)
        existing.update(records)
        storage.save_full_corpus(full_path, existing)
        storage.save_public_index(storage.public_index_path(family), existing)
        storage.write_manifest(storage.manifest_path(family), venue_family=family, records=existing, seed=None)
        print(f"  migrated {len(records)} forums into {family} ({full_path})")


def cmd_stats(args) -> None:
    corpus_path = Path(args.corpus)
    records = storage.load_corpus(corpus_path)
    if not records:
        sys.exit(f"no records found in {corpus_path}")

    corpus_hash = storage.corpus_hash(records)
    generated_at = statistics_mod.iso_now()
    stats = statistics_mod.compute_all_statistics(records, corpus_hash=corpus_hash, generated_at=generated_at)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    statistics_mod.write_statistics_json(out_dir / "statistics.json", stats, corpus_hash=corpus_hash, generated_at=generated_at)
    md = statistics_mod.render_markdown(stats, corpus_hash=corpus_hash, generated_at=generated_at)
    storage.atomic_write_text(out_dir / "statistics.md", md)

    print(f"wrote {len(stats)} statistics ({len(records)} forums) to {out_dir}")


def cmd_evidence(args) -> None:
    corpus_path = Path(args.corpus)
    records = storage.load_corpus(corpus_path)
    if not records:
        sys.exit(f"no records found in {corpus_path}")

    held_out_forum_ids = None
    if args.held_out:
        held_out_forum_ids = set(json.loads(Path(args.held_out).read_text()))

    corpus_hash = storage.corpus_hash(records)
    generated_at = statistics_mod.iso_now()
    try:
        items = evidence_mod.select_evidence(
            records,
            seed=args.seed,
            corpus_hash=corpus_hash,
            max_items=args.max_items,
            per_bucket=args.per_bucket,
            held_out_forum_ids=held_out_forum_ids,
        )
        evidence_mod.validate_evidence_bundle(items, records, held_out_forum_ids=held_out_forum_ids)
    except (ValueError, evidence_mod.EvidenceValidationError) as e:
        sys.exit(f"evidence generation failed: {e}")

    out_path = Path(args.output)
    evidence_mod.write_evidence_bundle(out_path, items, corpus_hash=corpus_hash, generated_at=generated_at, seed=args.seed)
    print(f"wrote {len(items)} evidence items to {out_path}")


def cmd_discover(args) -> None:
    client = get_client(args.api_version)
    inv = discover_review_invitation(client, args.venue_id, args.api_version)
    print(inv or "not found")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperscope",
        description="Fetch real OpenReview peer reviews and build a venue-calibrated reviewer skill.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch reviews from OpenReview")
    fetch_sub = fetch.add_subparsers(dest="fetch_command", required=True)

    venue_p = fetch_sub.add_parser("venue", help="Fetch/refresh a venue family")
    venue_p.add_argument("--family", nargs="+", required=True, metavar="FAMILY",
                          help="Venue families: iclr neurips icml acl cvpr aaai kdd")
    venue_p.add_argument("--years", nargs="+", metavar="YEAR", help="Years to include, e.g. 2025 2026")
    venue_p.add_argument("--papers", type=int, default=DEFAULT_PER_VENUE, metavar="N",
                          help=f"Unseen forums to fetch per venue-year (default: {DEFAULT_PER_VENUE})")
    venue_p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                          help=f"Seed for reproducible acquisition sampling (default: {DEFAULT_SEED})")
    venue_p.add_argument("--refresh-policy", choices=refresh_policy_mod.REFRESH_POLICIES, default="none",
                          help="'none' (default): only fetch unseen forums. 'active': also refresh "
                               "unresolved/active-cycle forums already in the corpus.")
    venue_p.add_argument("--refresh-limit", type=int, default=50,
                          help="Max forums to refresh per venue-year per run (default: 50)")
    venue_p.add_argument("--refresh-expiry-days", type=float, default=180,
                          help="Stop refreshing unresolved records older than this many days (default: 180)")
    venue_p.add_argument("--refresh-max-attempts", type=int, default=6,
                          help="Mark a forum unavailable after this many failed refresh attempts (default: 6)")
    venue_p.set_defaults(func=cmd_fetch_venue)

    forum_p = fetch_sub.add_parser("forum", help="Fetch a single forum by URL or ID")
    forum_p.add_argument("--url", required=True, help="Forum URL or raw forum ID")
    forum_p.set_defaults(func=cmd_fetch_forum)

    migrate_p = sub.add_parser("migrate", help="Import a legacy corpus_<family>.json into the new schema")
    migrate_p.add_argument("legacy_corpus", help="Path to the legacy corpus JSON file")
    migrate_p.set_defaults(func=cmd_migrate)

    discover_p = sub.add_parser("discover", help="Debug: discover a venue's review invitation ID")
    discover_p.add_argument("venue_id")
    discover_p.add_argument("--api-version", choices=["v1", "v2"], default="v2")
    discover_p.set_defaults(func=cmd_discover)

    stats_p = sub.add_parser("stats", help="Compute deterministic venue/year-scoped corpus statistics")
    stats_p.add_argument("--corpus", required=True, help="Path to a corpus JSONL file (full or public tier)")
    stats_p.add_argument("--output", default=str(ARTIFACTS_DIR / "statistics"),
                          help="Output directory for statistics.json + statistics.md")
    stats_p.set_defaults(func=cmd_stats)

    evidence_p = sub.add_parser("evidence", help="Generate a bounded, deterministic evidence bundle")
    evidence_p.add_argument("--corpus", required=True, help="Path to a full-text corpus JSONL file (data/full/)")
    evidence_p.add_argument("--output", default=str(ARTIFACTS_DIR / "evidence_bundle.json"),
                             help="Output path for the evidence bundle JSON file")
    evidence_p.add_argument("--seed", type=int, default=DEFAULT_SEED,
                             help=f"Seed for reproducible stratified sampling (default: {DEFAULT_SEED})")
    evidence_p.add_argument("--max-items", type=int, default=DEFAULT_EVIDENCE_MAX_ITEMS,
                             help=f"Max evidence items in the bundle (default: {DEFAULT_EVIDENCE_MAX_ITEMS})")
    evidence_p.add_argument("--per-bucket", type=int, default=DEFAULT_EVIDENCE_PER_BUCKET,
                             help=f"Max items sampled per stratification bucket (default: {DEFAULT_EVIDENCE_PER_BUCKET})")
    evidence_p.add_argument("--held-out", default=None,
                             help="Path to a JSON list of forum IDs to exclude (held-out evaluation set)")
    evidence_p.set_defaults(func=cmd_evidence)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    print(f"[paperscope] auth mode: {auth_mode()}", file=sys.stderr)
    args.func(args)


if __name__ == "__main__":
    main()
