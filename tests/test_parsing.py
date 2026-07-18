from paperscope.parsing import (
    build_forum_record,
    classify_invitation,
    get_field,
    get_field_list,
    get_field_str,
    normalize_decision,
    parse_rating,
)
from tests.conftest import make_decision_note, make_paper_note, make_review_note


def test_get_field_plain_string():
    assert get_field({"title": "Hello"}, "title") == "Hello"


def test_get_field_wrapped_value_dict():
    assert get_field({"title": {"value": "Hello"}}, "title") == "Hello"


def test_get_field_preserves_list_type():
    # regression test for the old bug: lists must NOT be str()'d into repr text
    result = get_field({"authors": {"value": ["Alice", "Bob"]}}, "authors")
    assert result == ["Alice", "Bob"]
    assert not isinstance(result, str)


def test_get_field_missing_key_returns_none():
    assert get_field({}, "authors") is None


def test_get_field_str_coerces_list():
    assert get_field_str({"authors": {"value": ["Alice", "Bob"]}}, "authors") == "Alice, Bob"


def test_get_field_list_joins_properly():
    joined = get_field_list({"keywords": {"value": ["a", "b", "c"]}}, "keywords")
    assert joined == "a, b, c"
    assert "[" not in joined  # not a Python repr


def test_parse_rating_extracts_value_and_label():
    r = parse_rating("6: marginally above the acceptance threshold")
    assert r.value == 6.0
    assert "marginally above" in r.label
    assert r.raw == "6: marginally above the acceptance threshold"


def test_parse_rating_handles_plain_number():
    r = parse_rating("7")
    assert r.value == 7.0


def test_parse_rating_handles_none():
    r = parse_rating(None)
    assert r.value is None
    assert r.raw == ""


def test_normalize_decision_accept_variants():
    assert normalize_decision("Accept (Oral)") == ("accept", "oral")
    assert normalize_decision("The paper is accepted for publication") == ("accept", "")


def test_normalize_decision_reject_variants():
    assert normalize_decision("Reject")[0] == "reject"
    assert normalize_decision("This submission is rejected")[0] == "reject"


def test_normalize_decision_withdrawn_and_desk_reject():
    assert normalize_decision("Withdrawn by authors")[0] == "withdrawn"
    assert normalize_decision("Desk Rejected")[0] == "desk_reject"


def test_normalize_decision_unknown_for_empty():
    assert normalize_decision("") == ("unknown", "")


def test_classify_invitation_review():
    assert classify_invitation("ICLR.cc/2026/Conference/-/Official_Review") == "review"


def test_classify_invitation_rebuttal():
    assert classify_invitation("ICLR.cc/2026/Conference/-/Rebuttal") == "rebuttal"


def test_classify_invitation_decision():
    assert classify_invitation("ICLR.cc/2026/Conference/-/Decision") == "decision"


def test_classify_invitation_other():
    assert classify_invitation("ICLR.cc/2026/Conference/-/Public_Comment") == "other"


def test_build_forum_record_groups_reviews_and_decision():
    paper = make_paper_note("f1")
    reviews = [make_review_note("r1", forum="f1"), make_review_note("r2", rating="3: reject", forum="f1")]
    decision = make_decision_note("f1", "Accept (poster)")

    record = build_forum_record(
        paper, reviews + [decision],
        venue_family="iclr", venue_id="ICLR.cc/2026/Conference", venue_year=2026, api_version="v2",
    )

    assert record.forum_id == "f1"
    assert len(record.reviews) == 2
    assert record.decision.normalized == "accept"
    assert record.decision.category == "poster"
    assert record.paper.title == "A Great Paper"
    assert record.paper.authors == "Alice, Bob"
