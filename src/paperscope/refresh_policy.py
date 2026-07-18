"""Refresh-candidate selection for already-fetched forums.

This is the "existing-forum refresh policy": scheduled fetching isn't just "unseen
forums forever" -- stored records need occasional re-checking for score/decision
changes, but bounded so the job's OpenReview traffic doesn't grow unbounded as the
corpus ages. This selection logic is plain, tested Python -- the CI workflow only ever
invokes `paperscope fetch venue --refresh-policy active`, it never decides selection
itself.
"""

from __future__ import annotations

import time

from paperscope.config import is_active_cycle_venue
from paperscope.models import TERMINAL_REASONS, ForumRecord

SECONDS_PER_HOUR = 3600
REFRESH_POLICIES = ("none", "active")

# Priority order when multiple refresh reasons compete for a limited per-run budget.
_PRIORITY = {"missing_decision": 0, "active_cycle": 1, "unresolved": 2, "stale": 3}


def compute_next_interval_hours(attempts: int, base_hours: float) -> float:
    """Exponential backoff on the refresh interval, capped at 2**6 = 64x the base."""
    return base_hours * (2 ** min(attempts, 6))


def _refresh_reason(record: ForumRecord, now: float, expiry_days: float) -> str | None:
    if record.decision.normalized in ("", "unknown"):
        return "missing_decision"
    if is_active_cycle_venue(record.venue_family, record.venue_year):
        return "active_cycle"
    return None  # has a real decision and isn't in an active cycle -- not a candidate


def select_candidates(
    records: list[ForumRecord],
    *,
    refresh_policy: str,
    now: float | None = None,
    expiry_days: float = 180,
) -> list[tuple[ForumRecord, str]]:
    """Return (record, reason) pairs eligible for refresh right now, priority-ordered.

    `refresh_policy="none"` returns nothing -- acquisition of unseen forums (sampling.py)
    is handled separately and always runs regardless of this policy.
    """
    if refresh_policy not in REFRESH_POLICIES:
        raise ValueError(f"unknown refresh policy: {refresh_policy!r}")
    if refresh_policy == "none":
        return []

    now = now if now is not None else time.time()
    selected = []
    for record in records:
        if record.refresh.status in TERMINAL_REASONS:
            continue
        if record.refresh.next_refresh_at is not None and now < record.refresh.next_refresh_at:
            continue
        reason = _refresh_reason(record, now, expiry_days)
        if reason:
            selected.append((record, reason))
    selected.sort(key=lambda pair: _PRIORITY.get(pair[1], 9))
    return selected


def apply_refresh_result(
    record: ForumRecord,
    *,
    fetched_ok: bool,
    changed: bool,
    now: float | None = None,
    max_attempts: int = 6,
    base_interval_hours: float = 24,
    expiry_days: float = 180,
) -> None:
    """Update `record.refresh` in place after a refresh attempt.

    Recognizes terminal states (finalized/withdrawn/desk_rejected/unavailable/
    refresh_expired) so finalized old records stop being repeatedly refreshed by default.
    """
    now = now if now is not None else time.time()
    record.refresh.last_checked_at = now

    if not fetched_ok:
        record.refresh.refresh_attempts += 1
        if record.refresh.refresh_attempts >= max_attempts:
            _mark_terminal(record, "unavailable")
        else:
            _schedule_next(record, now, base_interval_hours)
        return

    if record.decision.normalized == "withdrawn":
        _mark_terminal(record, "withdrawn")
        return
    if record.decision.normalized == "desk_reject":
        _mark_terminal(record, "desk_rejected")
        return

    active = is_active_cycle_venue(record.venue_family, record.venue_year)
    has_decision = record.decision.normalized in ("accept", "reject")

    if has_decision and not active:
        _mark_terminal(record, "finalized")
        return

    age_days = (now - record.fetched_at) / 86400 if record.fetched_at else 0
    if age_days > expiry_days and not active:
        _mark_terminal(record, "refresh_expired")
        return

    record.refresh.refresh_attempts = 0 if changed else record.refresh.refresh_attempts + 1
    record.refresh.status = "active" if active else "unresolved"
    record.refresh.terminal_reason = None
    _schedule_next(record, now, base_interval_hours)


def _schedule_next(record: ForumRecord, now: float, base_interval_hours: float) -> None:
    interval = compute_next_interval_hours(record.refresh.refresh_attempts, base_interval_hours)
    record.refresh.next_refresh_at = now + interval * SECONDS_PER_HOUR


def _mark_terminal(record: ForumRecord, reason: str) -> None:
    record.refresh.status = reason
    record.refresh.terminal_reason = reason
    record.refresh.next_refresh_at = None
