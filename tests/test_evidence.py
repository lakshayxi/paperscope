from collections import Counter
from pathlib import Path

from paperscope import storage
from paperscope.evidence import (
    EvidenceValidationError,
    evidence_id_for,
    is_public_tier,
    select_evidence,
    validate_evidence_bundle,
    write_evidence_bundle,
)
from paperscope.models import Decision, ForumRecord, Paper, Rating, Response, Review

REAL_CORPUS = Path(__file__).parent.parent / "data" / "full" / "iclr.jsonl"
PUBLIC_CORPUS = Path(__file__).parent.parent / "data" / "public" / "iclr.jsonl"


def _make_review(note_id, rating=None, text="Some review text.", strengths="", weaknesses="", summary=""):
    review = Review(
        note_id=note_id, text=text, strengths=strengths, weaknesses=weaknesses, summary=summary,
        initial_rating=Rating(raw=str(rating), value=rating) if rating is not None else Rating(),
    )
    review.content_hash = review.compute_hash()
    return review


def _forum(forum_id, *, family="ev", year=2025, reviews=None, responses=0, decision="unknown"):
    record = ForumRecord(
        forum_id=forum_id, url=f"https://openreview.net/forum?id={forum_id}",
        venue_family=family, venue_id=f"{family}.org/{year}", venue_year=year, api_version="v2",
        paper=Paper(title="T", abstract="A"),
        decision=Decision(raw_text=decision, normalized=decision),
        reviews=reviews or [],
    )
    for i in range(responses):
        record.responses.append(Response(note_id=f"{forum_id}_resp{i}", text="thanks"))
    return record


def _oversubscribed_records():
    """20 reviews across 10 forums, each axis has categories with far more than the
    default per_bucket=4 candidates -- needed to make seed-sensitivity meaningful (see
    test_select_evidence_differs_for_different_seed).
    """
    records = {}
    for i in range(10):
        reviews = [
            _make_review(f"f{i}_r1", rating=2 * i + 1),
            _make_review(f"f{i}_r2", rating=2 * i + 2),
        ]
        forum = _forum(f"f{i}", reviews=reviews, responses=1 if i % 2 == 0 else 0)
        records[forum.forum_id] = forum
    return records


def test_select_evidence_deterministic_for_same_seed():
    records = _oversubscribed_records()
    a = select_evidence(records, seed=42, corpus_hash="h1")
    b = select_evidence(records, seed=42, corpus_hash="h1")
    assert [i.evidence_id for i in a] == [i.evidence_id for i in b]


def test_select_evidence_differs_for_different_seed():
    records = _oversubscribed_records()
    a = select_evidence(records, seed=42, corpus_hash="h1")
    b = select_evidence(records, seed=7, corpus_hash="h1")
    assert [i.evidence_id for i in a] != [i.evidence_id for i in b]


def test_select_evidence_respects_max_items_bound():
    records = _oversubscribed_records()
    items = select_evidence(records, seed=42, corpus_hash="h1", max_items=10, per_bucket=4)
    assert len(items) == 10


def test_select_evidence_per_bucket_zero_returns_empty():
    records = _oversubscribed_records()
    items = select_evidence(records, seed=42, corpus_hash="h1", per_bucket=0)
    assert items == []


def test_select_evidence_empty_text_reviews_are_skipped():
    forum = _forum("only", reviews=[_make_review("r1", rating=5.0, text="", strengths="", weaknesses="", summary="")])
    items = select_evidence({"only": forum}, seed=42, corpus_hash="h1")
    assert items == []


def test_select_evidence_all_candidates_in_one_bucket_still_works():
    # every real ICLR record currently has decision == "unknown" -- mirror that degeneracy
    records = {
        f.forum_id: f
        for f in [_forum("x1", decision="unknown", reviews=[_make_review("r1", rating=4.0)]),
                  _forum("x2", decision="unknown", reviews=[_make_review("r2", rating=6.0)])]
    }
    items = select_evidence(records, seed=42, corpus_hash="h1")
    assert len(items) == 2
    assert {i.strata["decision_bucket"] for i in items} == {"unknown"}


def test_forum_note_pairs_never_duplicated():
    records = _oversubscribed_records()
    items = select_evidence(records, seed=42, corpus_hash="h1", max_items=1000, per_bucket=1000)
    pairs = [(i.forum_id, i.note_id) for i in items]
    assert len(pairs) == len(set(pairs))


def test_evidence_id_for_is_stable_across_seeds():
    records = _oversubscribed_records()
    a = select_evidence(records, seed=42, corpus_hash="h1", max_items=1000, per_bucket=1000)
    b = select_evidence(records, seed=7, corpus_hash="h1", max_items=1000, per_bucket=1000)
    by_pair_a = {(i.forum_id, i.note_id): i.evidence_id for i in a}
    by_pair_b = {(i.forum_id, i.note_id): i.evidence_id for i in b}
    assert by_pair_a == by_pair_b  # same underlying review -> same ID regardless of seed
    assert by_pair_a[("f0", "f0_r1")] == evidence_id_for("f0", "f0_r1", "initial")


def test_is_public_tier_detects_excerpted_corpus():
    full_records = storage.load_corpus(REAL_CORPUS)
    public_records = storage.load_corpus(PUBLIC_CORPUS)
    assert is_public_tier(full_records) is False
    assert is_public_tier(public_records) is True


def test_is_public_tier_false_even_with_empty_text_on_full_tier():
    forum = _forum("x", reviews=[_make_review("r1", rating=4.0, text="")])
    assert is_public_tier({"x": forum}) is False


def test_select_evidence_raises_on_public_tier():
    public_records = storage.load_corpus(PUBLIC_CORPUS)
    try:
        select_evidence(public_records, seed=42, corpus_hash="h1")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "full-text corpus tier" in str(e)


def test_held_out_forum_ids_excluded_from_output():
    records = _oversubscribed_records()
    held_out = {"f0", "f1", "f2"}
    items = select_evidence(records, seed=42, corpus_hash="h1", max_items=1000, per_bucket=1000, held_out_forum_ids=held_out)
    assert not any(i.forum_id in held_out for i in items)


def test_rating_tercile_bucket_assignment_matches_real_corpus_distribution():
    # {2.0: 8, 4.0: 17, 6.0: 8, 8.0: 4} -- ties lean toward "medium" (see module docstring)
    records = storage.load_corpus(REAL_CORPUS)
    items = select_evidence(records, seed=42, corpus_hash="h1", max_items=1000, per_bucket=1000)
    counts = Counter(i.strata["rating_bucket"] for i in items)
    assert counts == {"low": 8, "medium": 17, "high": 12}


def test_provenance_completeness_and_self_validation():
    records = storage.load_corpus(REAL_CORPUS)
    corpus_hash = storage.corpus_hash(records)
    items = select_evidence(records, seed=42, corpus_hash=corpus_hash)
    assert items  # sanity: the fixture actually produced something
    for item in items:
        assert item.evidence_id and item.venue_family and item.forum_id and item.note_id
        assert item.source_url and item.rating_designation in ("initial", "final")
        assert item.decision and item.content_hash and item.corpus_hash
        assert item.excerpt_length >= len(item.excerpt_text)
    validate_evidence_bundle(items, records)  # must not raise


def test_write_evidence_bundle_roundtrips_and_validates(tmp_path):
    records = storage.load_corpus(REAL_CORPUS)
    corpus_hash = storage.corpus_hash(records)
    items = select_evidence(records, seed=42, corpus_hash=corpus_hash)
    path = tmp_path / "bundle.json"
    payload = write_evidence_bundle(path, items, corpus_hash=corpus_hash, generated_at="t0", seed=42)
    assert payload["count"] == len(items)
    assert path.exists()


def _one_item(records=None):
    records = records or storage.load_corpus(REAL_CORPUS)
    corpus_hash = storage.corpus_hash(records)
    return select_evidence(records, seed=42, corpus_hash=corpus_hash)[0], records


def test_validate_rejects_content_hash_mismatch():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, content_hash="deadbeef")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "content hash" in str(e)


def test_validate_rejects_tampered_excerpt_text_with_hash_left_alone():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, excerpt_text="something the review never said")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "prefix" in str(e)


def test_validate_rejects_duplicate_evidence_ids():
    item, records = _one_item()
    try:
        validate_evidence_bundle([item, item], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "duplicate evidence_id" in str(e)


def test_validate_rejects_unknown_forum_id():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, forum_id="does-not-exist")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "unknown forum_id" in str(e)


def test_validate_rejects_unknown_note_id():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, note_id="does-not-exist")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "unknown note_id" in str(e)


def test_validate_rejects_unsupported_venue_year_claim():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, venue_year=1999)
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "unsupported venue/year claim" in str(e)


def test_validate_rejects_missing_provenance_field():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, source_url="")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "missing provenance field 'source_url'" in str(e)


def test_validate_rejects_held_out_overlap():
    item, records = _one_item()
    try:
        validate_evidence_bundle([item], records, held_out_forum_ids={item.forum_id})
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        assert "held-out" in str(e)


def test_validate_reports_every_violation_not_just_first():
    import dataclasses

    item, records = _one_item()
    bad = dataclasses.replace(item, content_hash="deadbeef", source_url="")
    try:
        validate_evidence_bundle([bad], records)
        raise AssertionError("expected EvidenceValidationError")
    except EvidenceValidationError as e:
        msg = str(e)
        assert "content hash" in msg
        assert "missing provenance field 'source_url'" in msg
