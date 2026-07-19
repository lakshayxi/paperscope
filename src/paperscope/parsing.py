"""Parse OpenReview notes into paper-centric ForumRecords.

Fixes the get_field bug from expl.py: the old version unconditionally `str()`d any
non-dict value before callers got a chance to see a real list, so author/keyword lists
were stringified as Python-repr text ("['A', 'B']") instead of being joined properly.
`get_field` now returns the value's native type (after unwrapping `{value: ...}` dicts);
`get_field_str`/`get_field_list` are explicit about how to coerce it.
"""

from __future__ import annotations

import re

from paperscope.models import Decision, ForumRecord, Paper, Rating, Response, Review

_REVIEW_RE = re.compile(r"/official[_-]?review$|/review$", re.I)
_REBUTTAL_RE = re.compile(r"/author|/rebuttal|/official_comment", re.I)
_DECISION_RE = re.compile(r"/meta_review$|/decision$", re.I)

_ACCEPT_RE = re.compile(r"\baccept(ed|ance|ing|s)?\b", re.I)
_REJECT_RE = re.compile(r"\breject(ed|ion|ing|s)?\b", re.I)
_WITHDRAW_RE = re.compile(r"\bwithdraw", re.I)
_DESK_RE = re.compile(r"\bdesk[\s-]?reject", re.I)
_CATEGORY_RE = re.compile(r"\b(oral|spotlight|poster)\b", re.I)

_VENUEID_WITHDRAWN_RE = re.compile(r"/Withdrawn_Submission$")
_VENUEID_DESK_REJECTED_RE = re.compile(r"/Desk_Rejected_Submission$")
_VENUEID_REJECTED_RE = re.compile(r"/Rejected_Submission$")
_VENUEID_ACTIVE_RE = re.compile(r"/Submission$")


def get_field(content: dict, key: str):
    """Return the raw value for `key`, unwrapped from a `{value: ...}` dict if needed.

    Preserves the original type (str, list, number) -- callers decide how to coerce it.
    """
    if not isinstance(content, dict):
        return None
    v = content.get(key)
    if isinstance(v, dict) and "value" in v:
        return v.get("value")
    return v


def get_field_str(content: dict, key: str) -> str:
    v = get_field(content, key)
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def get_field_list(content: dict, key: str) -> str:
    """Explicit multi-value coercion for fields like authors/keywords that are commonly
    lists in the OpenReview API -- joins into a single readable string.
    """
    v = get_field(content, key)
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def classify_invitation(inv) -> str:
    if isinstance(inv, list):
        inv = inv[0] if inv else ""
    inv = str(inv)
    if _REVIEW_RE.search(inv):
        return "review"
    if _REBUTTAL_RE.search(inv):
        return "rebuttal"
    if _DECISION_RE.search(inv):
        return "decision"
    return "other"


def parse_rating(raw) -> Rating:
    """Parse a venue rating string into raw/value/label, e.g.
    "6: marginally above the acceptance threshold" -> value=6.0, label="marginally above...".
    Scale bounds aren't derivable from the note alone (venues vary) and are left None;
    a future venue-metadata lookup could populate them.
    """
    if raw is None:
        return Rating()
    raw_str = str(raw) if not isinstance(raw, list) else ", ".join(str(x) for x in raw)
    m = re.search(r"[-+]?\d+(\.\d+)?", raw_str)
    value = float(m.group()) if m else None
    label = ""
    if ":" in raw_str:
        label = raw_str.split(":", 1)[1].strip()
    elif "-" in raw_str and m:
        label = raw_str.split("-", 1)[1].strip()
    return Rating(raw=raw_str, value=value, label=label)


def normalize_decision(raw_text: str) -> tuple[str, str]:
    """Return (normalized_outcome, category) from a raw decision/meta-review string."""
    if not raw_text:
        return "unknown", ""
    if _WITHDRAW_RE.search(raw_text):
        return "withdrawn", ""
    if _DESK_RE.search(raw_text):
        return "desk_reject", ""
    category_match = _CATEGORY_RE.search(raw_text)
    category = category_match.group(1).lower() if category_match else ""
    if _ACCEPT_RE.search(raw_text):
        return "accept", category
    if _REJECT_RE.search(raw_text):
        return "reject", category
    return "unknown", category


def parse_review_note(note) -> Review:
    c = note.content if isinstance(note.content, dict) else {}
    rating_raw = (
        get_field(c, "rating") or get_field(c, "recommendation")
        or get_field(c, "score") or get_field(c, "overall")
    )
    confidence_raw = get_field(c, "confidence")
    text = get_field_str(c, "review") or get_field_str(c, "comment") or get_field_str(c, "main_review")
    strengths = get_field_str(c, "strengths")
    weaknesses = get_field_str(c, "weaknesses")
    questions = get_field_str(c, "questions") or get_field_str(c, "limitations")
    review = Review(
        note_id=getattr(note, "id", None),
        invitation=str(getattr(note, "invitation", "") or getattr(note, "invitations", "") or ""),
        initial_rating=parse_rating(rating_raw),
        confidence=parse_rating(confidence_raw),
        summary=get_field_str(c, "summary") or get_field_str(c, "title"),
        text=text,
        strengths=strengths,
        weaknesses=weaknesses,
        questions=questions,
        modified_at=getattr(note, "mdate", None) or getattr(note, "tmdate", None),
    )
    review.content_hash = review.compute_hash()
    return review


def parse_response_note(note, kind: str) -> Response:
    c = note.content if isinstance(note.content, dict) else {}
    text = get_field_str(c, "comment") or get_field_str(c, "reply") or get_field_str(c, "text")
    response = Response(
        note_id=getattr(note, "id", None),
        kind=kind,
        text=text,
        modified_at=getattr(note, "mdate", None) or getattr(note, "tmdate", None),
    )
    response.content_hash = response.compute_hash()
    return response


def parse_decision_note(note) -> Decision:
    c = note.content if isinstance(note.content, dict) else {}
    raw_text = (
        get_field_str(c, "decision") or get_field_str(c, "metareview")
        or get_field_str(c, "comment") or get_field_str(c, "text")
    )
    normalized, category = normalize_decision(raw_text)
    return Decision(raw_text=raw_text, normalized=normalized, category=category, note_id=getattr(note, "id", None))


def decision_from_venueid(paper_note) -> Decision | None:
    """OpenReview's 2023+ venue schema records the *final* accept/reject/withdrawn/
    desk-reject outcome on the submission note itself, by rewriting its `venueid` (and
    human-readable `venue`) once decisions are finalized -- e.g.
    `ICLR.cc/2024/Conference/Submission` (active) -> `.../Rejected_Submission`,
    `.../Withdrawn_Submission`, `.../Desk_Rejected_Submission`, or the bare venue id with
    `venue` reading like "ICLR 2024 spotlight" (accepted). This is more authoritative
    than keyword-matching a separate Decision/Meta_Review note's free-text prose (see
    `normalize_decision`) -- a Meta_Review note commonly exists with no fixed-vocabulary
    verdict field, e.g. `content == {"metareview": "...", ...}` with no `decision`/
    `recommendation` value the old regex-only path could ever resolve, and a withdrawn
    submission may have no decision-shaped note at all. Returns None (not `Decision()`)
    when `venueid` is missing or still looks like an unresolved/active submission, so
    callers can fall back to note-based parsing or leave the decision unresolved rather
    than mistaking "no signal yet" for "unknown outcome".
    """
    c = paper_note.content if isinstance(paper_note.content, dict) else {}
    venueid = get_field_str(c, "venueid")
    venue = get_field_str(c, "venue")
    if not venueid:
        return None
    if _VENUEID_WITHDRAWN_RE.search(venueid):
        return Decision(raw_text=venue or venueid, normalized="withdrawn", note_id=None)
    if _VENUEID_DESK_REJECTED_RE.search(venueid):
        return Decision(raw_text=venue or venueid, normalized="desk_reject", note_id=None)
    if _VENUEID_REJECTED_RE.search(venueid):
        return Decision(raw_text=venue or venueid, normalized="reject", note_id=None)
    if _VENUEID_ACTIVE_RE.search(venueid):
        return None  # still an active/unresolved submission -- decisions not posted yet
    # venueid has been rewritten away from ".../Submission" and matches none of the
    # reject/withdrawn/desk-reject markers above -> accepted into the venue.
    category_match = _CATEGORY_RE.search(venue or "")
    category = category_match.group(1).lower() if category_match else ""
    return Decision(raw_text=venue or venueid, normalized="accept", category=category, note_id=None)


def parse_paper(note) -> dict:
    c = note.content if isinstance(note.content, dict) else {}
    return {
        "title": get_field_str(c, "title"),
        "abstract": get_field_str(c, "abstract"),
        "keywords": get_field_list(c, "keywords"),
        "authors": get_field_list(c, "authors"),
    }


def classify_and_split_children(child_notes) -> tuple[list, list, object | None]:
    """Split a forum's child notes into (review_notes, response_notes, decision_note)."""
    reviews, responses, decision_note = [], [], None
    for note in child_notes:
        inv = getattr(note, "invitation", "") or getattr(note, "invitations", "") or ""
        kind = classify_invitation(inv)
        if kind == "review":
            reviews.append(note)
        elif kind == "rebuttal":
            responses.append(note)
        elif kind == "decision":
            decision_note = note
    return reviews, responses, decision_note


def build_forum_record(
    paper_note,
    child_notes,
    *,
    venue_family: str,
    venue_id: str,
    venue_year: int | None,
    api_version: str,
    sampling_method: str = "",
    sampling_seed: int | None = None,
) -> ForumRecord:
    """Build one ForumRecord from a paper/submission note plus its child notes.

    Shared by both single-forum fetch and bulk acquisition -- fixes the old expl.py gap
    where bulk fetch never captured decisions/rebuttals even though single-forum fetch
    already knew how to.
    """
    forum_id = getattr(paper_note, "id", None) or getattr(paper_note, "forum", None)
    review_notes, response_notes, decision_note = classify_and_split_children(child_notes)

    record = ForumRecord(
        forum_id=forum_id,
        url=f"https://openreview.net/forum?id={forum_id}",
        venue_family=venue_family,
        venue_id=venue_id,
        venue_year=venue_year,
        api_version=api_version,
        paper=Paper(**parse_paper(paper_note)),
        reviews=[parse_review_note(n) for n in review_notes],
        responses=[parse_response_note(n, "rebuttal") for n in response_notes],
        sampling_method=sampling_method,
        sampling_seed=sampling_seed,
    )
    # venueid (see decision_from_venueid) is checked FIRST and wins whenever it resolves:
    # it's a structured, controlled-vocabulary field, whereas a Decision/Meta_Review
    # note's free text is keyword-matched and can be actively wrong, not just missing --
    # e.g. a meta-review reject ("the paper falls short of the acceptance threshold")
    # containing the word "acceptance" used to keyword-match as "accept". Only fall back
    # to note-based parsing when venueid gives no signal (older/v1 venues that predate
    # this convention, or a still-active submission with no venueid outcome yet).
    venueid_decision = decision_from_venueid(paper_note)
    if venueid_decision is not None:
        record.decision = venueid_decision
    elif decision_note is not None:
        record.decision = parse_decision_note(decision_note)
    return record
