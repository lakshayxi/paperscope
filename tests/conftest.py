from __future__ import annotations

from pathlib import Path

import pytest

from paperscope import storage
from paperscope.models import Decision, ForumRecord, Paper, Rating, Response, Review, content_hash

# --------------------------------------------------------------------------------------
# Synthetic full-text corpus fixtures.
#
# These stand in for the real, gitignored data/full/<family>.jsonl corpus so the default
# test suite never depends on locally-fetched OpenReview data. The corpus below is
# deliberately varied along every axis evidence.py stratifies on (decision, rating
# tercile, year, disagreement, rebuttal presence) plus statistics.py's grouping axes
# (venue/year scope, missing fields) so tests retain real behavioral coverage.
# --------------------------------------------------------------------------------------


def _syn_review(note_id, rating, *, confidence=4.0, final_rating=None,
                 text=None, strengths="Solid empirical results.",
                 weaknesses="Limited theoretical grounding.", summary="A reasonable contribution."):
    text = text if text is not None else f"Review {note_id}: the method is clearly described and evaluated."
    review = Review(
        note_id=note_id,
        invitation="synthetic.org/-/Official_Review",
        initial_rating=Rating(raw=str(rating), value=rating),
        confidence=Rating(raw=str(confidence), value=confidence),
        final_rating=Rating(raw=str(final_rating), value=final_rating) if final_rating is not None else None,
        text=text,
        strengths=strengths,
        weaknesses=weaknesses,
        summary=summary,
    )
    review.content_hash = review.compute_hash()
    return review


def _syn_forum(forum_id, *, family="iclr", year, decision, reviews, responses=0, title=None):
    record = ForumRecord(
        forum_id=forum_id,
        url=f"https://openreview.net/forum?id={forum_id}",
        venue_family=family,
        venue_id=f"{family}.org/{year}/Conference",
        venue_year=year,
        api_version="v2",
        paper=Paper(
            title=title or f"Synthetic Paper {forum_id}",
            abstract=f"A synthetic abstract for forum {forum_id}, used only in tests.",
            authors="Alice Example;Bob Example",
            keywords="deep learning;synthetic",
        ),
        decision=Decision(raw_text=decision, normalized=decision),
        reviews=reviews,
    )
    for i in range(responses):
        text = f"Thank you for the feedback on {forum_id}, response {i}."
        record.responses.append(Response(note_id=f"{forum_id}_resp{i}", text=text, content_hash=content_hash(text)))
    return record


def build_synthetic_forum_records() -> dict[str, ForumRecord]:
    """A deterministic synthetic corpus covering two venue years, all three decision
    outcomes, single- and multi-review forums, initial and final (revised) ratings, and
    forums with and without responses -- everything evidence/statistics tests exercise.
    """
    forums = [
        _syn_forum("f01", year=2024, decision="accept",
                   reviews=[_syn_review("f01_r1", 6.0, confidence=4.0), _syn_review("f01_r2", 8.0, confidence=3.0)],
                   responses=1),
        _syn_forum("f02", year=2024, decision="reject",
                   reviews=[_syn_review("f02_r1", 3.0, confidence=5.0)], responses=0),
        _syn_forum("f03", year=2024, decision="unknown",
                   reviews=[_syn_review("f03_r1", 5.0, confidence=4.0),
                            _syn_review("f03_r2", 5.0, confidence=2.0, final_rating=7.0),
                            _syn_review("f03_r3", 7.0, confidence=3.0)],
                   responses=0),
        _syn_forum("f04", year=2024, decision="accept",
                   reviews=[_syn_review("f04_r1", 9.0, confidence=5.0)], responses=1),
        _syn_forum("f05", year=2024, decision="reject",
                   reviews=[_syn_review("f05_r1", 2.0, confidence=4.0), _syn_review("f05_r2", 4.0, confidence=3.0)],
                   responses=0),
        _syn_forum("f06", year=2024, decision="unknown",
                   reviews=[_syn_review("f06_r1", 6.0, confidence=3.0)], responses=1),
        _syn_forum("f07", year=2025, decision="accept",
                   reviews=[_syn_review("f07_r1", 8.0, confidence=4.0),
                            _syn_review("f07_r2", 7.0, confidence=5.0, final_rating=8.0)],
                   responses=1),
        _syn_forum("f08", year=2025, decision="reject",
                   reviews=[_syn_review("f08_r1", 2.0, confidence=3.0), _syn_review("f08_r2", 1.0, confidence=4.0)],
                   responses=0),
        _syn_forum("f09", year=2025, decision="unknown",
                   reviews=[_syn_review("f09_r1", 5.0, confidence=5.0), _syn_review("f09_r2", 6.0, confidence=4.0)],
                   responses=0),
        _syn_forum("f10", year=2025, decision="accept",
                   reviews=[_syn_review("f10_r1", 9.0, confidence=5.0),
                            _syn_review("f10_r2", 10.0, confidence=4.0, final_rating=9.0)],
                   responses=1),
        _syn_forum("f11", year=2025, decision="reject",
                   reviews=[_syn_review("f11_r1", 3.0, confidence=3.0)], responses=0),
        _syn_forum("f12", year=2024, decision="unknown",
                   reviews=[_syn_review("f12_r1", 4.0, confidence=3.0), _syn_review("f12_r2", 8.0, confidence=2.0)],
                   responses=0),
    ]
    return {f.forum_id: f for f in forums}


@pytest.fixture
def synthetic_forum_records() -> dict[str, ForumRecord]:
    return build_synthetic_forum_records()


@pytest.fixture
def full_corpus_path(tmp_path: Path, synthetic_forum_records: dict[str, ForumRecord]) -> Path:
    path = tmp_path / "full" / "iclr.jsonl"
    storage.save_full_corpus(path, synthetic_forum_records)
    return path


@pytest.fixture
def public_corpus_path(tmp_path: Path, synthetic_forum_records: dict[str, ForumRecord]) -> Path:
    path = tmp_path / "public" / "iclr.jsonl"
    storage.save_public_index(path, synthetic_forum_records)
    return path


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
