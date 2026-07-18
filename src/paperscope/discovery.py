"""Discover a venue's review invitation ID.

Moved from expl.py's `discover_review_invitation` with no behavioral change -- confirmed
via research that OpenReview API v2 has no venue-wide "list all reviews" shortcut beyond
what this already does (probe common suffixes, then fall back to listing invitations by
domain/prefix and regex-matching).
"""

from __future__ import annotations

import itertools
import re

from paperscope.openreview_client import get_client

_REVIEW_RE = re.compile(r"/official[_-]?review$|/review$", re.I)


def discover_review_invitation(client, venue_id: str, version: str) -> str | None:
    """Return the review invitation ID for a venue, or None on total failure.

    1. Fast path: probe /-/Official_Review then /-/Review with a small limit.
    2. Slow path: list all invitations and regex-match for a review pattern.
    3. Cross-version fallback: if the given version fails, retry with the other client.
    """

    def _probe(c, ver: str) -> str | None:
        for suffix in ("Official_Review", "Review"):
            inv = f"{venue_id}/-/{suffix}"
            try:
                if ver == "v2":
                    notes = list(itertools.islice(c.get_all_notes(invitation=inv), 1))
                else:
                    notes = c.get_notes(invitation=inv, limit=1)
                if notes:
                    return inv
            except Exception:
                pass
            try:
                c.get_invitation(inv)
                return inv
            except Exception as e:
                err = str(e)
                if "403" in err or "Forbidden" in err or "permission" in err.lower():
                    return inv  # invitation exists, metadata just restricted
        try:
            if ver == "v2":
                invs = c.get_all_invitations(domain=venue_id)
                if not invs:
                    invs = c.get_all_invitations(prefix=venue_id)
            else:
                invs = c.get_invitations(regex=re.escape(venue_id) + ".*")
            for inv in invs:
                if _REVIEW_RE.search(inv.id):
                    return inv.id
        except Exception:
            pass
        return None

    result = _probe(client, version)
    if result:
        return result

    other_version = "v1" if version == "v2" else "v2"
    try:
        result = _probe(get_client(other_version), other_version)
    except Exception:
        result = None
    return result
