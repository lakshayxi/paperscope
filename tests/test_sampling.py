from paperscope.sampling import (
    VenueCursor,
    discover_submission_invitation,
    fetch_unseen_submissions,
)
from tests.conftest import FakeNote

SUB_INV = "ICLR.cc/2026/Conference/-/Blind_Submission"


class FakeV2Client:
    """Simulates enough of OpenReviewClient.get_notes/get_all_notes for pagination tests."""

    def __init__(self, submissions):
        self._submissions = submissions  # ordered oldest-first, as tcdate:asc would return

    def get_all_notes(self, invitation=None):
        if invitation == SUB_INV:
            return iter(self._submissions)
        return iter([])

    def get_notes(self, invitation=None, after=None, sort=None, limit=None, offset=None):
        if invitation != SUB_INV:
            return []
        start = 0
        if after is not None:
            ids = [n.id for n in self._submissions]
            start = ids.index(after) + 1 if after in ids else 0
        return self._submissions[start : start + (limit or len(self._submissions))]


def _submissions(n=10):
    return [FakeNote(id=f"sub{i}") for i in range(n)]


def test_discover_submission_invitation_finds_blind_submission():
    client = FakeV2Client(_submissions(3))
    inv = discover_submission_invitation(client, "ICLR.cc/2026/Conference", "v2")
    assert inv == SUB_INV


def test_fetch_unseen_submissions_first_call_returns_from_start():
    client = FakeV2Client(_submissions(10))
    cursor = VenueCursor()
    selected, new_cursor = fetch_unseen_submissions(
        client, "ICLR.cc/2026/Conference", "v2", n=3, cursor=cursor, seen_forum_ids=set()
    )
    assert [n.id for n in selected] == ["sub0", "sub1", "sub2"]
    assert new_cursor.last_note_id is not None


def test_fetch_unseen_submissions_resumes_past_previous_batch():
    """Regression test for the old bug: repeated calls must NOT keep returning the same
    first n notes -- the cursor must advance so a second call makes progress.

    Uses a submission pool larger than the acquisition over-fetch batch (50) so the
    first call doesn't already exhaust the whole test venue.
    """
    client = FakeV2Client(_submissions(120))
    cursor = VenueCursor()

    first_batch, cursor = fetch_unseen_submissions(
        client, "ICLR.cc/2026/Conference", "v2", n=3, cursor=cursor, seen_forum_ids=set()
    )
    seen = {n.id for n in first_batch}

    second_batch, cursor = fetch_unseen_submissions(
        client, "ICLR.cc/2026/Conference", "v2", n=3, cursor=cursor, seen_forum_ids=seen
    )

    first_ids = {n.id for n in first_batch}
    second_ids = {n.id for n in second_batch}
    assert first_ids.isdisjoint(second_ids), "second call re-fetched the same notes as the first"
    assert len(second_batch) == 3


def test_fetch_unseen_submissions_dedups_against_seen_ids():
    client = FakeV2Client(_submissions(10))
    cursor = VenueCursor()
    seen = {"sub0", "sub1"}
    selected, _cursor = fetch_unseen_submissions(
        client, "ICLR.cc/2026/Conference", "v2", n=3, cursor=cursor, seen_forum_ids=seen
    )
    assert not ({n.id for n in selected} & seen)


def test_fetch_unseen_submissions_is_deterministic_for_same_seed():
    client_a = FakeV2Client(_submissions(10))
    client_b = FakeV2Client(_submissions(10))
    selected_a, _ = fetch_unseen_submissions(
        client_a, "ICLR.cc/2026/Conference", "v2", n=5, cursor=VenueCursor(), seen_forum_ids=set(), seed=42
    )
    selected_b, _ = fetch_unseen_submissions(
        client_b, "ICLR.cc/2026/Conference", "v2", n=5, cursor=VenueCursor(), seen_forum_ids=set(), seed=42
    )
    assert [n.id for n in selected_a] == [n.id for n in selected_b]


def test_fetch_unseen_submissions_no_submission_invitation_returns_empty():
    class EmptyClient:
        def get_all_notes(self, invitation=None):
            return iter([])

        def get_notes(self, **kwargs):
            return []

    selected, cursor = fetch_unseen_submissions(
        EmptyClient(), "Unknown.cc/2026/Conference", "v2", n=5, cursor=VenueCursor(), seen_forum_ids=set()
    )
    assert selected == []
