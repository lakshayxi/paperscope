import json
from pathlib import Path

from paperscope import storage
from paperscope.models import Decision, ForumRecord, Paper, Rating, Response, Review
from paperscope.statistics import (
    compute_all_statistics,
    group_by_scope,
    render_markdown,
    write_statistics_json,
)

REAL_CORPUS = Path(__file__).parent.parent / "data" / "full" / "iclr.jsonl"


def _review(note_id, rating, confidence=None, final_rating=None):
    return Review(
        note_id=note_id,
        initial_rating=Rating(raw=str(rating), value=rating),
        confidence=Rating(raw=str(confidence), value=confidence) if confidence is not None else Rating(),
        final_rating=Rating(raw=str(final_rating), value=final_rating) if final_rating is not None else None,
    )


def _forum(forum_id, *, family="testv", year=2025, title="A Paper", abstract="An abstract",
           reviews=None, decision="unknown", responses=0):
    record = ForumRecord(
        forum_id=forum_id, url=f"https://openreview.net/forum?id={forum_id}",
        venue_family=family, venue_id=f"{family}.org/{year}", venue_year=year, api_version="v2",
        paper=Paper(title=title, abstract=abstract),
        decision=Decision(raw_text=decision, normalized=decision),
        reviews=reviews or [],
    )
    for i in range(responses):
        record.responses.append(Response(note_id=f"{forum_id}_resp{i}", text="thanks"))
    return record


def _fixture_records():
    # forum A: 2 reviews (6, 4), one revised (4 -> 6), accepted, has a rebuttal response
    forum_a = _forum(
        "A", year=2025, decision="accept", responses=1,
        reviews=[
            _review("r1", 6.0, confidence=4.0),
            _review("r2", 4.0, confidence=2.0, final_rating=6.0),
        ],
    )
    # forum B: 1 review (8), rejected, no responses -- too few reviews for variance/disagreement
    forum_b = _forum("B", year=2025, decision="reject", responses=0, reviews=[_review("r3", 8.0, confidence=5.0)])
    # forum C: no reviews at all, missing title/abstract/decision -- exercises missing-rate paths
    forum_c = _forum("C", year=2026, title="", abstract="", decision="unknown", reviews=[])
    return {"A": forum_a, "B": forum_b, "C": forum_c}


def _stat(stats, metric, family, year):
    matches = [s for s in stats if s.metric == metric and s.venue_family == family and s.venue_year == year]
    assert len(matches) == 1, f"expected exactly one {metric}/{family}/{year}, got {len(matches)}"
    return matches[0]


def test_group_by_scope_splits_by_year_and_adds_family_aggregate():
    scopes = group_by_scope(_fixture_records())
    assert set(scopes) == {("testv", 2025), ("testv", 2026), ("testv", "all")}
    assert {r.forum_id for r in scopes[("testv", 2025)]} == {"A", "B"}
    assert {r.forum_id for r in scopes[("testv", 2026)]} == {"C"}
    assert {r.forum_id for r in scopes[("testv", "all")]} == {"A", "B", "C"}


def test_forum_review_response_counts_exact():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    forum_count = _stat(stats, "forum_count", "testv", 2025)
    assert forum_count.sample_size == 2 and forum_count.missing_count == 0 and forum_count.value == 2

    review_count = _stat(stats, "review_count", "testv", 2025)
    assert review_count.sample_size == 2 and review_count.missing_count == 0 and review_count.value == 3

    response_count = _stat(stats, "response_count", "testv", 2025)
    assert response_count.value == 1 and response_count.missing_count == 1  # forum B has none

    # forum C has zero reviews -- both counts must reflect that as "missing"
    review_count_c = _stat(stats, "review_count", "testv", 2026)
    assert review_count_c.sample_size == 1 and review_count_c.missing_count == 1 and review_count_c.value == 0


def test_missing_rate_paper_fields_and_zero_denominator():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    title_2025 = _stat(stats, "missing_rate.paper_title", "testv", 2025)
    assert title_2025.value == 0.0  # A and B both have titles

    title_2026 = _stat(stats, "missing_rate.paper_title", "testv", 2026)
    assert title_2026.sample_size == 1 and title_2026.missing_count == 1 and title_2026.value == 1.0

    # forum C contributes zero reviews -- the review-rating missing-rate denominator is 0
    rating_missing_2026 = _stat(stats, "missing_rate.review_rating", "testv", 2026)
    assert rating_missing_2026.sample_size == 0 and rating_missing_2026.value is None


def test_rating_and_confidence_distribution_raw_histograms_exact():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    rating_hist = _stat(stats, "rating_distribution_raw", "testv", 2025)
    assert rating_hist.sample_size == 3
    assert rating_hist.value == {"4.0": 1, "6.0": 1, "8.0": 1}

    conf_hist = _stat(stats, "confidence_distribution_raw", "testv", 2025)
    assert conf_hist.value == {"2.0": 1, "4.0": 1, "5.0": 1}


def test_rating_scales_are_scope_isolated_across_venues():
    records = _fixture_records()
    records["D"] = _forum(
        "D", family="otherv", year=2025, decision="unknown",
        reviews=[_review("d1", 1.0), _review("d2", 3.0), _review("d3", 6.0)],
    )
    stats = compute_all_statistics(records, corpus_hash="abc123", generated_at="t0")

    testv_hist = _stat(stats, "rating_distribution_raw", "testv", 2025)
    assert testv_hist.value == {"4.0": 1, "6.0": 1, "8.0": 1}  # unaffected by otherv's 1-6 scale

    otherv_hist = _stat(stats, "rating_distribution_raw", "otherv", 2025)
    assert otherv_hist.value == {"1.0": 1, "3.0": 1, "6.0": 1}

    # otherv's normalized decile buckets are min-max scaled against ITS OWN range (1-6),
    # not blended with testv's (4-8) range
    otherv_norm = _stat(stats, "rating_distribution_normalized", "otherv", 2025)
    assert otherv_norm.value["0.0-0.1"] == 1  # value 1.0 -> normalized 0.0
    assert otherv_norm.value["0.9-1.0"] == 1  # value 6.0 -> normalized 1.0


def test_paper_mean_rating_and_variance_exact():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    means = _stat(stats, "paper_mean_rating", "testv", 2025)
    # forum A mean = (6+4)/2 = 5.0, forum B mean = 8.0
    assert means.sample_size == 2 and means.missing_count == 0
    assert means.value["mean"] == 6.5 and means.value["min"] == 5.0 and means.value["max"] == 8.0

    variances = _stat(stats, "paper_rating_variance", "testv", 2025)
    # only forum A has >=2 reviews: pvariance([6, 4]) == 1.0
    assert variances.sample_size == 1 and variances.missing_count == 1  # forum B excluded
    assert variances.value["mean"] == 1.0 and variances.value["min"] == 1.0 and variances.value["max"] == 1.0


def test_reviewer_disagreement_range_and_histogram_bucket():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    disagreement = _stat(stats, "reviewer_disagreement", "testv", 2025)
    # only forum A has >=2 reviews: range = 6 - 4 = 2
    assert disagreement.sample_size == 1
    assert disagreement.value["mean"] == 2.0
    assert disagreement.value["histogram"] == {"0": 0, "1-2": 1, "3-4": 0, "5+": 0}


def test_initial_to_final_rating_change_exact():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    change = _stat(stats, "initial_to_final_rating_change", "testv", 2025)
    # 3 reviews total, only r2 (forum A) was revised: 4 -> 6, delta = +2
    assert change.sample_size == 3 and change.missing_count == 2
    assert change.value["count"] == 1 and change.value["mean"] == 2.0
    assert change.observational is False


def test_rebuttal_present_vs_absent_split_is_observational():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="abc123", generated_at="t0")

    present = _stat(stats, "rebuttal_present_rating_change", "testv", 2025)
    absent = _stat(stats, "rebuttal_absent_rating_change", "testv", 2025)

    # forum A (2 reviews, 1 revised) has a response; forum B (1 review, 0 revised) doesn't
    assert present.sample_size == 2 and present.value["count"] == 1 and present.value["mean"] == 2.0
    assert absent.sample_size == 1 and absent.value["count"] == 0

    for s in (present, absent):
        assert s.observational is True
        assert s.note and "not causal" in s.note


def test_every_stat_carries_required_provenance_fields():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="somehash", generated_at="2026-01-01T00:00:00Z")
    for s in stats:
        assert s.corpus_hash == "somehash"
        assert s.generated_at == "2026-01-01T00:00:00Z"
        assert s.schema_version == 1
        assert s.venue_family and s.venue_year is not None
        assert s.sample_size >= 0 and s.missing_count >= 0


def test_render_markdown_is_deterministic_and_order_independent():
    stats = compute_all_statistics(_fixture_records(), corpus_hash="h1", generated_at="t0")
    md1 = render_markdown(stats, corpus_hash="h1", generated_at="t0")
    md2 = render_markdown(stats, corpus_hash="h1", generated_at="t0")
    assert md1 == md2

    md_shuffled = render_markdown(list(reversed(stats)), corpus_hash="h1", generated_at="t0")
    assert md1 == md_shuffled


def test_write_statistics_json_roundtrips(tmp_path):
    stats = compute_all_statistics(_fixture_records(), corpus_hash="h1", generated_at="t0")
    path = tmp_path / "statistics.json"
    write_statistics_json(path, stats, corpus_hash="h1", generated_at="t0")

    payload = json.loads(path.read_text())
    assert payload["corpus_hash"] == "h1"
    assert payload["stat_count"] == len(stats)
    assert len(payload["stats"]) == len(stats)


def test_smoke_against_real_corpus():
    records = storage.load_corpus(REAL_CORPUS)
    corpus_hash = storage.corpus_hash(records)
    stats = compute_all_statistics(records, corpus_hash=corpus_hash, generated_at="t0")
    assert len(stats) > 0
    forum_count = _stat(stats, "forum_count", "iclr", "all")
    assert forum_count.value == len(records)
