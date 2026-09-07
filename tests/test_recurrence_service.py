import datetime

from services.recurrence_service import (
    compute_next_occurrence,
    compute_repost_time,
    evaluate_repost_readiness,
    is_lobby_expired,
    should_auto_archive_event,
)
from utils.enums import EventStatus


def test_compute_next_occurrence_daily_and_weekly():
    """Test daily, weekly, and biweekly recurrence calculations."""
    base_dt = datetime.datetime(2026, 6, 1, 18, 0, 0, tzinfo=datetime.timezone.utc)
    base_ts = base_dt.timestamp()

    # Daily: exactly 24 hours later
    daily_conf = {"recurrence_type": "daily", "timezone": "UTC"}
    next_ts = compute_next_occurrence(base_ts, daily_conf)
    next_dt = datetime.datetime.fromtimestamp(next_ts, tz=datetime.timezone.utc)
    assert next_dt == base_dt + datetime.timedelta(days=1)

    # Weekly: exactly 7 days later
    weekly_conf = {"recurrence_type": "weekly", "timezone": "UTC"}
    next_weekly_ts = compute_next_occurrence(base_ts, weekly_conf)
    next_weekly_dt = datetime.datetime.fromtimestamp(next_weekly_ts, tz=datetime.timezone.utc)
    assert next_weekly_dt == base_dt + datetime.timedelta(weeks=1)

    # Biweekly: exactly 14 days later
    biweekly_conf = {"recurrence_type": "biweekly", "timezone": "UTC"}
    next_biweekly_ts = compute_next_occurrence(base_ts, biweekly_conf)
    next_biweekly_dt = datetime.datetime.fromtimestamp(next_biweekly_ts, tz=datetime.timezone.utc)
    assert next_biweekly_dt == base_dt + datetime.timedelta(weeks=2)

def test_compute_next_occurrence_custom_days():
    """Test custom weekday recurrence pattern (e.g. Mon=0, Wed=2, Fri=4)."""
    # 2026-06-01 is Monday (weekday 0)
    monday_dt = datetime.datetime(2026, 6, 1, 19, 0, 0, tzinfo=datetime.timezone.utc)
    monday_ts = monday_dt.timestamp()

    custom_conf = {
        "recurrence_type": "custom",
        "custom_days": "0, 2, 4", # Mon, Wed, Fri
        "timezone": "UTC"
    }

    # Next after Monday should be Wednesday (2 days later)
    wed_ts = compute_next_occurrence(monday_ts, custom_conf)
    wed_dt = datetime.datetime.fromtimestamp(wed_ts, tz=datetime.timezone.utc)
    assert wed_dt.weekday() == 2
    assert wed_dt.day == 3

    # Next after Friday (4) should wrap around to Monday (0)
    fri_dt = datetime.datetime(2026, 6, 5, 19, 0, 0, tzinfo=datetime.timezone.utc)
    fri_ts = fri_dt.timestamp()
    next_mon_ts = compute_next_occurrence(fri_ts, custom_conf)
    next_mon_dt = datetime.datetime.fromtimestamp(next_mon_ts, tz=datetime.timezone.utc)
    assert next_mon_dt.weekday() == 0
    assert next_mon_dt.day == 8

def test_compute_repost_time_triggers():
    """Test calculating repost timestamps based on before_start, after_start, and after_end."""
    start_dt = datetime.datetime(2026, 6, 1, 18, 0, 0, tzinfo=datetime.timezone.utc)
    start_ts = start_dt.timestamp()
    end_ts = start_ts + 7200 # 2 hour event

    conf = {"recurrence_type": "daily", "timezone": "UTC"}

    # after_start with 1h offset
    repost_after_start = compute_repost_time(start_ts, end_ts, "after_start", "1h", conf)
    assert repost_after_start == start_ts + 3600

    # after_end with 30m offset
    repost_after_end = compute_repost_time(start_ts, end_ts, "after_end", "30m", conf)
    assert repost_after_end == end_ts + 1800

    # before_start with 2h offset from next occurrence (next occurrence is start_ts + 86400)
    repost_before_start = compute_repost_time(start_ts, end_ts, "before_start", "2h", conf)
    assert repost_before_start == (start_ts + 86400) - 7200

def test_evaluate_repost_readiness():
    """Test checking if a recurring event is ready for next iteration."""
    start_ts = 1780000000.0
    db_event = {
        "start_time": start_ts,
        "recurrence_type": "daily",
        "repost_trigger": "after_start",
        "repost_offset": "1h",
        "recurrence_limit": 5,
        "recurrence_count": 1,
    }

    # Case 1: Too early (now is before start + 1h)
    now_early = start_ts + 1000
    ready, next_ts, status = evaluate_repost_readiness(db_event, {}, now_early)
    assert ready is False
    assert next_ts is None

    # Case 2: Time reached
    now_ready = start_ts + 4000
    ready, next_ts, status = evaluate_repost_readiness(db_event, {}, now_ready)
    assert ready is True
    assert next_ts is not None
    assert status is None

    # Case 3: Recurrence limit reached
    db_event_limited = dict(db_event, recurrence_limit=3, recurrence_count=2)
    ready, next_ts, status = evaluate_repost_readiness(db_event_limited, {}, now_ready)
    assert ready is False
    assert status == "closed"

def test_should_auto_archive_event():
    """Test auto-archival evaluation for finished one-time events respecting archive_hours grace period."""
    now = 1780100000.0

    # Event with end_time in the past, beyond archive_hours threshold (1 hour threshold, ended 2 hours ago)
    ended_event_archived = {
        "status": EventStatus.ACTIVE,
        "recurrence_type": "once",
        "start_time": now - 10800, # started 3h ago
        "end_time": now - 7200,    # ended 2h ago
        "created_at": now - 20000,
    }
    assert should_auto_archive_event(ended_event_archived, now, archive_hours=1.0) is True

    # Event ended recently (30 min ago), but server has 12h auto-archive grace period -> NOT archived yet
    ended_event_in_grace_period = {
        "status": EventStatus.ACTIVE,
        "recurrence_type": "once",
        "start_time": now - 7200,
        "end_time": now - 1800,    # ended 30m ago
        "created_at": now - 20000,
    }
    assert should_auto_archive_event(ended_event_in_grace_period, now, archive_hours=12.0) is False

    # Event still ongoing
    ongoing_event = {
        "status": EventStatus.ACTIVE,
        "recurrence_type": "once",
        "start_time": now - 1800,
        "end_time": now + 1800,
        "created_at": now - 3600,
    }
    assert should_auto_archive_event(ongoing_event, now, archive_hours=1.0) is False

    # Recurring events should not be auto-archived by this rule
    recurring_event = {
        "status": EventStatus.ACTIVE,
        "recurrence_type": "daily",
        "start_time": now - 20000,
        "end_time": now - 15000,
        "created_at": now - 30000,
    }
    assert should_auto_archive_event(recurring_event, now, archive_hours=1.0) is False

def test_is_lobby_expired():
    """Test expiration check for fill-to-start lobby events."""
    now = 1780000000.0

    # Expired lobby
    expired_lobby = {
        "lobby_mode": True,
        "status": EventStatus.ACTIVE,
        "start_time": None,
        "lobby_expires_at": now - 100,
    }
    assert is_lobby_expired(expired_lobby, now) is True

    # Non-expired lobby
    active_lobby = {
        "lobby_mode": True,
        "status": EventStatus.ACTIVE,
        "start_time": None,
        "lobby_expires_at": now + 500,
    }
    assert is_lobby_expired(active_lobby, now) is False

    # Lobby that already started (has start_time set) is not expired
    started_lobby = {
        "lobby_mode": True,
        "status": EventStatus.ACTIVE,
        "start_time": now - 50,
        "lobby_expires_at": now - 100,
    }
    assert is_lobby_expired(started_lobby, now) is False
