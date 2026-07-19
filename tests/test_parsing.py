from paperscope.parsing import (
    build_forum_record,
    classify_invitation,
    decision_from_venueid,
    get_field,
    get_field_list,
    get_field_str,
    normalize_decision,
    parse_rating,
)
from tests.conftest import FakeNote, make_decision_note, make_paper_note, make_review_note


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


# --------------------------------------------------------------------------------------
# decision_from_venueid: OpenReview 2023+ venue schema records the final outcome on the
# submission note's own venueid/venue fields, not only via a separate Decision note.
# Regression coverage for a real bug found fetching ICLR 2024: 24/67 fetched forums were
# withdrawn (no Decision note at all, so the old code left them "unknown" instead of
# "withdrawn"), and at least one meta-review's free text ("the paper falls short of the
# acceptance threshold") keyword-matched to "accept" via the old note-only regex parser
# even though the paper was actually rejected -- venueid must take priority, not just
# fill gaps, or a wrong verdict silently wins over a correct one.
# --------------------------------------------------------------------------------------


def _paper_with_venueid(venueid, venue=None):
    return FakeNote(id="f1", forum="f1", content={
        "title": {"value": "A Paper"}, "abstract": {"value": "..."},
        "venueid": {"value": venueid}, **({"venue": {"value": venue}} if venue else {}),
    })


def test_decision_from_venueid_active_submission_returns_none():
    assert decision_from_venueid(_paper_with_venueid("ICLR.cc/2024/Conference/Submission")) is None


def test_decision_from_venueid_missing_field_returns_none():
    assert decision_from_venueid(make_paper_note("f1")) is None


def test_decision_from_venueid_withdrawn():
    d = decision_from_venueid(_paper_with_venueid("ICLR.cc/2024/Conference/Withdrawn_Submission", "ICLR 2024 Conference Withdrawn Submission"))
    assert d.normalized == "withdrawn"


def test_decision_from_venueid_desk_rejected():
    d = decision_from_venueid(_paper_with_venueid("ICLR.cc/2024/Conference/Desk_Rejected_Submission"))
    assert d.normalized == "desk_reject"


def test_decision_from_venueid_rejected():
    d = decision_from_venueid(_paper_with_venueid("ICLR.cc/2024/Conference/Rejected_Submission", "Submitted to ICLR 2024"))
    assert d.normalized == "reject"


def test_decision_from_venueid_accepted_with_category():
    d = decision_from_venueid(_paper_with_venueid("ICLR.cc/2024/Conference", "ICLR 2024 spotlight"))
    assert d.normalized == "accept"
    assert d.category == "spotlight"


def test_venueid_wins_over_a_wrong_meta_review_keyword_match():
    """Regression test for the exact real-world bug: a meta-review's reject rationale
    happens to contain the substring "acceptance" ("falls short of the acceptance
    threshold"), which the old note-only regex parser matched as an accept. venueid says
    reject and must win.
    """
    paper = _paper_with_venueid("ICLR.cc/2024/Conference/Rejected_Submission", "Submitted to ICLR 2024")
    decision_note = FakeNote(
        id="f1_meta", forum="f1", invitation="ICLR.cc/2024/Conference/Submission1/-/Meta_Review",
        content={"metareview": {"value": "The paper falls short of the acceptance threshold and is not ready for publication."}},
    )
    record = build_forum_record(
        paper, [decision_note], venue_family="iclr", venue_id="ICLR.cc/2024/Conference", venue_year=2024, api_version="v2"
    )
    assert record.decision.normalized == "reject"


def test_venueid_fills_in_when_no_decision_note_exists_at_all():
    """A withdrawn submission commonly has no Decision/Meta_Review note at all -- venueid
    must still resolve it correctly rather than leaving normalized == "" (unresolved)."""
    paper = _paper_with_venueid("ICLR.cc/2024/Conference/Withdrawn_Submission", "ICLR 2024 Conference Withdrawn Submission")
    record = build_forum_record(
        paper, [], venue_family="iclr", venue_id="ICLR.cc/2024/Conference", venue_year=2024, api_version="v2"
    )
    assert record.decision.normalized == "withdrawn"


def test_note_based_parsing_still_used_when_venueid_absent():
    """Older/v1-API venues without the venueid convention must keep working exactly as
    before -- no regression for existing (non-venueid) fetched/migrated data."""
    paper = make_paper_note("f1")  # no venueid field
    decision = make_decision_note("f1", "Accept (oral)")
    record = build_forum_record(
        paper, [decision], venue_family="iclr", venue_id="ICLR.cc/2026/Conference", venue_year=2026, api_version="v2"
    )
    assert record.decision.normalized == "accept"
    assert record.decision.category == "oral"


def test_normalize_decision_now_catches_ing_and_s_accept_reject_forms():
    # regression: the original regex missed "accepting"/"rejecting"/"accepts"/"rejects"
    assert normalize_decision("the AC recommend accepting this work")[0] == "accept"
    assert normalize_decision("the committee is rejecting this submission")[0] == "reject"
