from paperscope.models import Decision, ForumRecord
from paperscope.refresh_policy import (
    apply_refresh_result,
    compute_next_interval_hours,
    select_candidates,
)

NOW = 1_800_000_000.0
DAY = 86400


def make_record(*, family="iclr", year=2024, decision_normalized="", forum_id="f1"):
    record = ForumRecord(
        forum_id=forum_id, url="https://x", venue_family=family, venue_id=f"{family}.cc",
        venue_year=year, api_version="v2",
    )
    record.decision = Decision(normalized=decision_normalized, raw_text=decision_normalized)
    record.fetched_at = NOW - 30 * DAY
    return record


def test_select_candidates_none_policy_returns_nothing():
    records = [make_record(decision_normalized="")]
    assert select_candidates(records, refresh_policy="none", now=NOW) == []


def test_select_candidates_flags_missing_decision():
    records = [make_record(decision_normalized="")]
    selected = select_candidates(records, refresh_policy="active", now=NOW)
    assert len(selected) == 1
    assert selected[0][1] == "missing_decision"


def test_select_candidates_flags_active_cycle_even_with_decision():
    records = [make_record(family="iclr", year=2026, decision_normalized="accept")]
    selected = select_candidates(records, refresh_policy="active", now=NOW)
    assert len(selected) == 1
    assert selected[0][1] == "active_cycle"


def test_select_candidates_excludes_finalized_old_record():
    record = make_record(family="iclr", year=2023, decision_normalized="accept")
    record.refresh.status = "finalized"
    record.refresh.terminal_reason = "finalized"
    selected = select_candidates([record], refresh_policy="active", now=NOW)
    assert selected == []


def test_select_candidates_respects_next_refresh_at_cooldown():
    record = make_record(decision_normalized="")
    record.refresh.next_refresh_at = NOW + DAY
    selected = select_candidates([record], refresh_policy="active", now=NOW)
    assert selected == []


def test_apply_refresh_result_finalizes_closed_cycle_with_decision():
    record = make_record(family="iclr", year=2023, decision_normalized="accept")
    apply_refresh_result(record, fetched_ok=True, changed=True, now=NOW)
    assert record.refresh.status == "finalized"
    assert record.refresh.terminal_reason == "finalized"
    assert record.refresh.next_refresh_at is None


def test_apply_refresh_result_keeps_active_cycle_unresolved_scheduled():
    record = make_record(family="iclr", year=2026, decision_normalized="")
    apply_refresh_result(record, fetched_ok=True, changed=True, now=NOW)
    assert record.refresh.status == "active"
    assert record.refresh.next_refresh_at is not None
    assert record.refresh.next_refresh_at > NOW


def test_apply_refresh_result_marks_withdrawn_terminal():
    record = make_record(decision_normalized="withdrawn")
    apply_refresh_result(record, fetched_ok=True, changed=False, now=NOW)
    assert record.refresh.status == "withdrawn"
    assert record.refresh.terminal_reason == "withdrawn"


def test_apply_refresh_result_marks_desk_rejected_terminal():
    record = make_record(decision_normalized="desk_reject")
    apply_refresh_result(record, fetched_ok=True, changed=False, now=NOW)
    assert record.refresh.status == "desk_rejected"


def test_apply_refresh_result_expires_old_unresolved_non_active():
    record = make_record(family="iclr", year=2023, decision_normalized="")
    record.fetched_at = NOW - 400 * DAY
    apply_refresh_result(record, fetched_ok=True, changed=False, now=NOW, expiry_days=180)
    assert record.refresh.status == "refresh_expired"
    assert record.refresh.next_refresh_at is None


def test_apply_refresh_result_failed_fetch_increments_attempts_until_unavailable():
    record = make_record(decision_normalized="")
    for _ in range(5):
        apply_refresh_result(record, fetched_ok=False, changed=False, now=NOW, max_attempts=6)
        assert record.refresh.status != "unavailable"
    apply_refresh_result(record, fetched_ok=False, changed=False, now=NOW, max_attempts=6)
    assert record.refresh.status == "unavailable"
    assert record.refresh.terminal_reason == "unavailable"


def test_apply_refresh_result_resets_attempts_when_changed():
    record = make_record(family="iclr", year=2026, decision_normalized="")
    record.refresh.refresh_attempts = 3
    apply_refresh_result(record, fetched_ok=True, changed=True, now=NOW)
    assert record.refresh.refresh_attempts == 0


def test_compute_next_interval_hours_grows_and_caps():
    base = 24
    assert compute_next_interval_hours(0, base) == 24
    assert compute_next_interval_hours(1, base) == 48
    assert compute_next_interval_hours(2, base) == 96
    capped = compute_next_interval_hours(20, base)
    assert capped == compute_next_interval_hours(6, base)  # capped at 2**6
