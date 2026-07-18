"""Corpus *acquisition* -- deterministic/seeded traversal of unseen forums.

This is intentionally narrow: it decides which forums to fetch next, not how to
interpret or stratify them once fetched. Rating/decision/year/disagreement-based
stratification belongs to evidence selection (a later phase), which runs after labels
are known -- a forum's decision or even its final rating may not exist yet at fetch time,
so acquisition must not assume it can filter on those fields.

Fixes the v2 pagination bug in the old expl.py: `get_all_notes()` restarts its internal
generator from the beginning of the stream on every call, so slicing it with `islice`
re-fetched the same first n notes forever. Here we call `get_notes(after=..., sort=...)`
directly and persist the last-seen note id as a cursor across runs.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

SUBMISSION_SUFFIXES = ("Blind_Submission", "Submission", "Camera_Ready_Revision", "Research")


@dataclass
class VenueCursor:
    """Persisted acquisition position for one venue-id, so a later run resumes instead
    of re-fetching the same notes. v2 advances via `last_note_id` (an `after` cursor);
    v1 has no native `after` and advances via a numeric `offset`.
    """
    last_note_id: str | None = None
    offset: int = 0

    def to_dict(self) -> dict:
        return {"last_note_id": self.last_note_id, "offset": self.offset}

    @classmethod
    def from_dict(cls, d: dict | None) -> VenueCursor:
        d = d or {}
        return cls(last_note_id=d.get("last_note_id"), offset=d.get("offset", 0))


def discover_submission_invitation(client, venue_id: str, version: str) -> str | None:
    for suffix in SUBMISSION_SUFFIXES:
        inv = f"{venue_id}/-/{suffix}"
        try:
            if version == "v2":
                notes = list(itertools.islice(client.get_all_notes(invitation=inv), 1))
            else:
                notes = client.get_notes(invitation=inv, limit=1)
            if notes:
                return inv
        except Exception:
            continue
    return None


def fetch_unseen_submissions(
    client,
    venue_id: str,
    version: str,
    n: int,
    cursor: VenueCursor,
    seen_forum_ids: set[str],
    seed: int | None = None,
) -> tuple[list, VenueCursor]:
    """Return up to `n` submission notes not in `seen_forum_ids`, plus the advanced cursor.

    Primary path (v2, submission invitation found): deterministic oldest-first traversal
    using a real `after` cursor -- no seed needed, order is stable across runs.
    Fallback path (v1, or v2 with no discoverable submission invitation): offset-based
    paging with a seeded shuffle among the fetched page, since v1 has no `after` cursor
    and ordering isn't guaranteed stable -- the seed makes repeated runs reproducible
    rather than randomly re-picking from the same page.
    """
    sub_inv = discover_submission_invitation(client, venue_id, version)
    if not sub_inv:
        return [], cursor

    if version == "v2":
        fetch_n = max(n * 3, 50)  # over-fetch since some will already be seen
        notes = client.get_notes(
            invitation=sub_inv, after=cursor.last_note_id, sort="tcdate:asc", limit=fetch_n
        )
        unseen = [note for note in notes if getattr(note, "id", None) not in seen_forum_ids]
        selected = unseen[:n]
        new_cursor = VenueCursor(last_note_id=notes[-1].id, offset=0) if notes else cursor
        return selected, new_cursor

    # v1 fallback: offset-based, seeded shuffle for reproducible selection.
    fetch_n = max(n * 3, 50)
    notes = client.get_notes(invitation=sub_inv, limit=fetch_n, offset=cursor.offset)
    if not notes and cursor.offset > 0:
        notes = client.get_notes(invitation=sub_inv, limit=fetch_n, offset=0)
        new_offset = len(notes)
    else:
        new_offset = cursor.offset + len(notes)
    rng = random.Random(seed)
    unseen = [note for note in notes if getattr(note, "id", None) not in seen_forum_ids]
    rng.shuffle(unseen)
    selected = unseen[:n]
    return selected, VenueCursor(last_note_id=None, offset=new_offset)
