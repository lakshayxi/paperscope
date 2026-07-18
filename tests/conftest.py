from __future__ import annotations

import pytest


class FakeNote:
    """Duck-types openreview.Note closely enough for parsing/sampling tests."""

    def __init__(self, id, content=None, invitation="", invitations=None, mdate=None, forum=None):
        self.id = id
        self.content = content or {}
        self.invitation = invitation
        self.invitations = invitations or ([invitation] if invitation else [])
        self.mdate = mdate
        self.forum = forum or id


def make_review_note(note_id, rating="6: marginally above the acceptance threshold",
                      confidence="4: confident", strengths="Good.", weaknesses="Weak.",
                      forum=None):
    return FakeNote(
        id=note_id,
        forum=forum,
        invitation="ICLR.cc/2026/Conference/-/Official_Review",
        content={
            "rating": {"value": rating},
            "confidence": {"value": confidence},
            "strengths": {"value": strengths},
            "weaknesses": {"value": weaknesses},
        },
        mdate=1700000000000,
    )


def make_paper_note(forum_id, title="A Great Paper", authors=None, keywords=None):
    return FakeNote(
        id=forum_id,
        forum=forum_id,
        content={
            "title": {"value": title},
            "abstract": {"value": "We propose..."},
            "authors": {"value": authors or ["Alice", "Bob"]},
            "keywords": {"value": keywords or ["deep learning", "theory"]},
        },
    )


def make_decision_note(forum_id, decision_text="Accept (poster)"):
    return FakeNote(
        id=f"{forum_id}_decision",
        forum=forum_id,
        invitation="ICLR.cc/2026/Conference/-/Decision",
        content={"decision": {"value": decision_text}},
    )


@pytest.fixture
def review_note():
    return make_review_note("rev1")


@pytest.fixture
def paper_note():
    return make_paper_note("forum1")
