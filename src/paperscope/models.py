"""Paper-centric corpus schema.

One `ForumRecord` per OpenReview forum/paper, nesting its reviews, responses, and
decision -- not one row per review. Ratings and decisions keep both the raw value as
reported by OpenReview and a normalized/derived value, since venues use inconsistent
scales and label text (see `Rating`/`Decision` below).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field

from paperscope import __version__ as PAPERSCOPE_VERSION
from paperscope.config import SCHEMA_VERSION

TERMINAL_REASONS = (
    "finalized",       # decision present, cycle closed, not expected to change again
    "withdrawn",
    "desk_rejected",
    "unavailable",     # forum could not be fetched (deleted, permissions, etc.)
    "refresh_expired",  # unresolved but too old to keep re-checking (see refresh_policy)
)

REFRESH_STATUSES = ("unseen", "active", "unresolved", "stale") + TERMINAL_REASONS


def content_hash(*parts: str) -> str:
    """Deterministic short hash over one or more text fields, for change detection."""
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


@dataclass
class Rating:
    """A single reported score, kept as both raw and normalized values.

    Venues differ in scale (1-10, 1-6, accept/reject-style labels, etc) -- storing only
    a parsed float loses the label and scale context needed to interpret it correctly.
    """
    raw: str = ""
    value: float | None = None
    label: str = ""
    scale_min: float | None = None
    scale_max: float | None = None


@dataclass
class Decision:
    """A forum's decision, kept as both the raw venue-specific text and a normalized
    outcome so downstream code can compare across venues without re-parsing prose.
    """
    raw_text: str = ""
    normalized: str = ""  # one of: accept, reject, withdrawn, desk_reject, unknown
    category: str = ""    # optional venue-specific detail, e.g. "oral", "poster", "spotlight"
    note_id: str | None = None


@dataclass
class Review:
    note_id: str
    invitation: str = ""
    initial_rating: Rating = field(default_factory=Rating)
    final_rating: Rating | None = None  # set only if the review was revised
    confidence: Rating = field(default_factory=Rating)
    summary: str = ""
    text: str = ""
    strengths: str = ""
    weaknesses: str = ""
    questions: str = ""
    modified_at: float | None = None
    content_hash: str = ""

    def compute_hash(self) -> str:
        return content_hash(self.text, self.strengths, self.weaknesses, self.questions)


@dataclass
class Response:
    note_id: str
    kind: str = "comment"  # "rebuttal" | "comment"
    text: str = ""
    modified_at: float | None = None
    content_hash: str = ""

    def compute_hash(self) -> str:
        return content_hash(self.text)


@dataclass
class RefreshState:
    """Tracks when/whether a forum record should be re-fetched. Lives on ForumRecord so
    the refresh policy (refresh_policy.py) can select candidates without re-deriving this
    from scratch on every run.
    """
    status: str = "unseen"        # see REFRESH_STATUSES
    terminal_reason: str | None = None
    last_checked_at: float | None = None
    refresh_attempts: int = 0
    next_refresh_at: float | None = None


@dataclass
class Paper:
    title: str = ""
    abstract: str = ""
    keywords: str = ""
    authors: str = ""


@dataclass
class ForumRecord:
    forum_id: str
    url: str
    venue_family: str
    venue_id: str
    venue_year: int | None
    api_version: str

    paper: Paper = field(default_factory=Paper)
    decision: Decision = field(default_factory=Decision)
    reviews: list[Review] = field(default_factory=list)
    responses: list[Response] = field(default_factory=list)

    schema_version: int = SCHEMA_VERSION
    fetched_at: float = field(default_factory=time.time)
    paperscope_version: str = PAPERSCOPE_VERSION

    sampling_method: str = ""
    sampling_seed: int | None = None
    retrieval_errors: list[str] = field(default_factory=list)

    refresh: RefreshState = field(default_factory=RefreshState)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ForumRecord:
        d = dict(d)
        paper_raw = d.pop("paper", None)
        paper = Paper(**paper_raw) if isinstance(paper_raw, dict) else Paper()
        decision_raw = d.pop("decision", None)
        decision = Decision(**decision_raw) if isinstance(decision_raw, dict) else Decision()
        reviews = [
            Review(
                **{
                    **r,
                    "initial_rating": Rating(**(r.get("initial_rating") or {})),
                    "final_rating": Rating(**r["final_rating"]) if r.get("final_rating") else None,
                    "confidence": Rating(**(r.get("confidence") or {})),
                }
            )
            for r in d.pop("reviews", [])
        ]
        responses = [Response(**r) for r in d.pop("responses", [])]
        refresh_raw = d.pop("refresh", None)
        refresh = RefreshState(**refresh_raw) if isinstance(refresh_raw, dict) else RefreshState()
        return cls(paper=paper, decision=decision, reviews=reviews, responses=responses, refresh=refresh, **d)
