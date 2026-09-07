import datetime

from services.recurrence_service import (
    compute_next_occurrence,
    evaluate_repost_readiness,
)
from utils.enums import EventStatus


def test_compute_next_occurrence_weekdays():
    """Test weekdays recurrence correctly advances Friday to Monday."""
    # 2026-06-05 is Friday
    fri_dt = datetime.datetime(2026, 6, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
    fri_ts = fri_dt.timestamp()

    conf = {"recurrence_type": "weekdays", "timezone": "UTC"}
    next_ts = compute_next_occurrence(fri_ts, conf)
    next_dt = datetime.datetime.fromtimestamp(next_ts, tz=datetime.timezone.utc)

    # Should be Monday 2026-06-08 (weekday 0)
    assert next_dt.weekday() == 0
    assert next_dt.day == 8

def test_compute_next_occurrence_weekends():
    """Test weekends recurrence advances Sunday to Saturday."""
    # 2026-06-07 is Sunday (weekday 6)
    sun_dt = datetime.datetime(2026, 6, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
    sun_ts = sun_dt.timestamp()

    conf = {"recurrence_type": "weekends", "timezone": "UTC"}
    next_ts = compute_next_occurrence(sun_ts, conf)
    next_dt = datetime.datetime.fromtimestamp(next_ts, tz=datetime.timezone.utc)

    # Should be Saturday 2026-06-13 (weekday 5)
    assert next_dt.weekday() == 5
    assert next_dt.day == 13

def test_compute_next_occurrence_monthly():
    """Test monthly recurrence advances by one month."""
    base_dt = datetime.datetime(2026, 3, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
    base_ts = base_dt.timestamp()

    conf = {"recurrence_type": "monthly", "timezone": "UTC"}
    next_ts = compute_next_occurrence(base_ts, conf)
    next_dt = datetime.datetime.fromtimestamp(next_ts, tz=datetime.timezone.utc)

    assert next_dt.month == 4
    assert next_dt.day == 15
    assert next_dt.hour == 10

def test_compute_next_occurrence_relative():
    """Test relative monthly recurrence (e.g., 1st Monday, last Friday of next month)."""
    # 2026-05-10 is in May 2026
    may_dt = datetime.datetime(2026, 5, 10, 15, 0, 0, tzinfo=datetime.timezone.utc)
    may_ts = may_dt.timestamp()

    # 1st Monday of June 2026 (June 1, 2026 is Monday)
    first_mon_conf = {
        "recurrence_type": "relative",
        "relative_combo": "wk_first,day_monday",
        "timezone": "UTC",
    }
    next_ts = compute_next_occurrence(may_ts, first_mon_conf)
    next_dt = datetime.datetime.fromtimestamp(next_ts, tz=datetime.timezone.utc)
    assert next_dt.month == 6
    assert next_dt.day == 1
    assert next_dt.weekday() == 0

    # Last Friday of June 2026 (June 26, 2026 is Friday)
    last_fri_conf = {
        "recurrence_type": "relative",
        "relative_combo": "wk_last,day_friday",
        "timezone": "UTC",
    }
    next_fri_ts = compute_next_occurrence(may_ts, last_fri_conf)
    next_fri_dt = datetime.datetime.fromtimestamp(next_fri_ts, tz=datetime.timezone.utc)
    assert next_fri_dt.month == 6
    assert next_fri_dt.day == 26
    assert next_fri_dt.weekday() == 4

def test_evaluate_repost_readiness_with_limit_date_and_lobby():
    """Test evaluate_repost_readiness handles recurrence_limit_date and lobby mode."""
    # 1. Lobby mode should immediately return (False, None, None)
    lobby_event = {"lobby_mode": True, "start_time": 1780000000}
    ready, _, _ = evaluate_repost_readiness(lobby_event, {}, 1780005000)
    assert ready is False

    # 2. recurrence_limit_date reached
    start_ts = 1780000000.0
    limit_date_ts = start_ts + 50000 # limit is before next daily occurrence (86400)
    event_with_limit = {
        "start_time": start_ts,
        "recurrence_type": "daily",
        "repost_trigger": "after_start",
        "repost_offset": "1h",
        "extra_data": f'{{"recurrence_limit_date": {limit_date_ts}}}',
    }
    ready, _, status = evaluate_repost_readiness(event_with_limit, {}, start_ts + 4000)
    assert ready is False
    assert status == EventStatus.CLOSED
