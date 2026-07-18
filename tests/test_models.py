from paperscope.models import Decision, ForumRecord, Rating, Response, Review, content_hash


def test_content_hash_deterministic():
    assert content_hash("a", "b") == content_hash("a", "b")


def test_content_hash_changes_with_content():
    assert content_hash("a", "b") != content_hash("a", "c")


def test_content_hash_handles_none_parts():
    assert content_hash(None, "b") == content_hash("", "b")


def test_review_compute_hash_reflects_text_fields():
    r1 = Review(note_id="r1", text="hello", strengths="s", weaknesses="w", questions="q")
    r2 = Review(note_id="r1", text="different", strengths="s", weaknesses="w", questions="q")
    assert r1.compute_hash() != r2.compute_hash()


def test_response_compute_hash():
    resp = Response(note_id="c1", text="a comment")
    assert resp.compute_hash() == content_hash("a comment")


def test_forum_record_roundtrip_preserves_nested_reviews_and_decision():
    record = ForumRecord(
        forum_id="f1", url="https://x", venue_family="iclr", venue_id="ICLR.cc/2026/Conference",
        venue_year=2026, api_version="v2",
    )
    record.reviews.append(Review(note_id="r1", initial_rating=Rating(raw="6", value=6.0)))
    record.decision = Decision(raw_text="Accept", normalized="accept", category="oral")

    restored = ForumRecord.from_dict(record.to_dict())

    assert restored.forum_id == "f1"
    assert len(restored.reviews) == 1
    assert restored.reviews[0].initial_rating.value == 6.0
    assert restored.decision.normalized == "accept"
    assert restored.decision.category == "oral"


def test_forum_record_defaults_are_empty_not_none():
    record = ForumRecord(
        forum_id="f1", url="https://x", venue_family="iclr", venue_id="x", venue_year=2024, api_version="v2",
    )
    assert record.reviews == []
    assert record.responses == []
    assert record.decision.normalized == ""
    assert record.refresh.status == "unseen"


def test_forum_record_from_dict_handles_missing_optional_sections():
    minimal = {
        "forum_id": "f1", "url": "https://x", "venue_family": "iclr",
        "venue_id": "x", "venue_year": 2024, "api_version": "v2",
    }
    record = ForumRecord.from_dict(minimal)
    assert record.reviews == []
    assert record.paper.title == ""
