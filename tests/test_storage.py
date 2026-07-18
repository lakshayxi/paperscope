from pathlib import Path

from paperscope.models import Decision, ForumRecord, Rating, Review
from paperscope.storage import (
    corpus_hash,
    load_corpus,
    migrate_legacy_corpus,
    save_full_corpus,
    save_public_index,
    to_public_dict,
    write_manifest,
)

FIXTURE = Path(__file__).parent / "fixtures" / "legacy_corpus_sample.json"


def _sample_record(forum_id="f1"):
    record = ForumRecord(
        forum_id=forum_id, url="https://x", venue_family="iclr", venue_id="ICLR.cc/2026/Conference",
        venue_year=2026, api_version="v2",
    )
    record.reviews.append(
        Review(note_id="r1", initial_rating=Rating(raw="6", value=6.0), text="Full review text " * 50)
    )
    record.decision = Decision(raw_text="Accept", normalized="accept")
    return record


def test_atomic_full_corpus_roundtrip(tmp_path):
    path = tmp_path / "iclr.jsonl"
    records = {"f1": _sample_record("f1"), "f2": _sample_record("f2")}
    save_full_corpus(path, records)

    loaded = load_corpus(path)
    assert set(loaded) == {"f1", "f2"}
    assert loaded["f1"].reviews[0].text == records["f1"].reviews[0].text


def test_public_index_strips_full_text_to_excerpt(tmp_path):
    path = tmp_path / "iclr.public.jsonl"
    record = _sample_record("f1")
    save_public_index(path, {"f1": record}, excerpt_max_chars=20)

    loaded = load_corpus(path)
    review = loaded["f1"].reviews[0]
    # after round-tripping through the public tier, `text` becomes the excerpt dict shape,
    # not the original full string
    assert isinstance(review.text, dict)
    assert len(review.text["excerpt"]) <= 20
    assert review.text["length"] == len(record.reviews[0].text)


def test_public_index_round_trip_twice_is_idempotent(tmp_path):
    """Regression test: CI restores the public index as its working corpus each run (the
    full-text tier is never persisted across runs), so re-saving already-excerpted
    records back to the public index must not crash or double-excerpt them.
    """
    path = tmp_path / "iclr.jsonl"
    record = _sample_record("f1")
    save_public_index(path, {"f1": record}, excerpt_max_chars=20)

    loaded_once = load_corpus(path)
    save_public_index(path, loaded_once, excerpt_max_chars=20)  # simulates a second CI run

    loaded_twice = load_corpus(path)
    review = loaded_twice["f1"].reviews[0]
    assert review.text["length"] == len(record.reviews[0].text)
    assert review.text["excerpt"] == loaded_once["f1"].reviews[0].text["excerpt"]


def test_to_public_dict_keeps_numeric_fields_in_full():
    record = _sample_record("f1")
    public = to_public_dict(record, excerpt_max_chars=10)
    assert public["reviews"][0]["initial_rating"]["value"] == 6.0
    assert public["decision"]["normalized"] == "accept"


def test_corpus_hash_is_deterministic_and_order_independent():
    records_a = {"f1": _sample_record("f1"), "f2": _sample_record("f2")}
    records_b = {"f2": _sample_record("f2"), "f1": _sample_record("f1")}
    assert corpus_hash(records_a) == corpus_hash(records_b)


def test_corpus_hash_changes_when_content_changes():
    records = {"f1": _sample_record("f1")}
    h1 = corpus_hash(records)
    records["f1"].reviews.append(Review(note_id="r2"))
    h2 = corpus_hash(records)
    assert h1 != h2


def test_write_manifest_reports_counts(tmp_path):
    path = tmp_path / "iclr.manifest.json"
    records = {"f1": _sample_record("f1"), "f2": _sample_record("f2")}
    manifest = write_manifest(path, venue_family="iclr", records=records, seed=42)
    assert manifest["record_count"] == 2
    assert manifest["review_count"] == 2
    assert manifest["seed"] == 42
    assert path.exists()


def test_migrate_legacy_corpus_groups_by_forum_and_family():
    by_family = migrate_legacy_corpus(FIXTURE)
    assert "iclr" in by_family
    records = by_family["iclr"]
    assert set(records) == {"forumA", "forumB"}
    assert len(records["forumA"].reviews) == 2
    assert len(records["forumB"].reviews) == 1
    assert records["forumA"].venue_year == 2024
    # paper metadata is unknown for migrated bulk-review-only data, not invented
    assert records["forumA"].paper.title == ""


def test_migrate_legacy_corpus_preserves_note_ids_for_evidence_tracing():
    by_family = migrate_legacy_corpus(FIXTURE)
    note_ids = {r.note_id for r in by_family["iclr"]["forumA"].reviews}
    assert note_ids == {"rev_a1", "rev_a2"}


def test_migrate_legacy_corpus_missing_file_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        migrate_legacy_corpus(Path("/nonexistent/legacy.json"))
