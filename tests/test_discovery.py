from paperscope.discovery import discover_review_invitation


class FakeInvitation:
    def __init__(self, id):
        self.id = id


class FakeClient:
    def __init__(self, notes_by_invitation=None, invitations=None, raise_forbidden_for=None):
        self._notes = notes_by_invitation or {}
        self._invitations = invitations or []
        self._raise_forbidden_for = raise_forbidden_for or set()

    def get_all_notes(self, invitation=None):
        if invitation in self._raise_forbidden_for:
            raise Exception("403 Forbidden")
        return iter(self._notes.get(invitation, []))

    def get_notes(self, invitation=None, limit=None):
        return self._notes.get(invitation, [])

    def get_invitation(self, inv):
        if inv in self._raise_forbidden_for:
            raise Exception("403 Forbidden")
        raise Exception("not found")

    def get_all_invitations(self, domain=None, prefix=None):
        return [FakeInvitation(i) for i in self._invitations]


def test_discover_finds_official_review_via_notes():
    inv = "V.cc/2026/Conference/-/Official_Review"
    client = FakeClient(notes_by_invitation={inv: ["note1"]})
    result = discover_review_invitation(client, "V.cc/2026/Conference", "v2")
    assert result == inv


def test_discover_treats_403_as_invitation_exists():
    inv = "V.cc/2026/Conference/-/Official_Review"
    client = FakeClient(raise_forbidden_for={inv})
    result = discover_review_invitation(client, "V.cc/2026/Conference", "v2")
    assert result == inv


def test_discover_falls_back_to_invitation_listing():
    # Uses a suffix the direct probe never tries ("Official_Review"/"Review" literally)
    # but which still matches the review regex via a dash separator, so it can only be
    # found through the get_all_invitations fallback.
    inv = "V.cc/2026/Conference/-/official-review"
    client = FakeClient(invitations=[inv])
    result = discover_review_invitation(client, "V.cc/2026/Conference", "v2")
    assert result == inv


def test_discover_returns_none_on_total_failure():
    client = FakeClient()
    result = discover_review_invitation(client, "V.cc/2026/Conference", "v2")
    assert result is None
