import time
import datetime
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from utils.calendar_utils import (
    get_google_calendar_url,
    generate_ics_batch,
)
from utils.templates import get_template_data
from utils.enums import EventStatus
from services.recurrence_service import (
    compute_next_occurrence,
    compute_repost_time,
    evaluate_repost_readiness,
    should_auto_archive_event,
)
from database.repositories.reminders import (
    normalize_reminders_for_store,
    replace_event_reminders,
)

def test_integration_event_creation_to_calendar_and_ics():
    """Integration: Event data definition -> Template parsing -> Calendar URL & Batch ICS generation."""
    event_id = "EVT-INTEG-001"
    title = "Guild Progression Raid"
    desc = "Weekly Mythic raid\nBring flasks and food"
    start_dt = datetime.datetime(2026, 9, 15, 19, 0, 0, tzinfo=datetime.timezone.utc)
    start_ts = start_dt.timestamp()
    end_ts = start_ts + 10800 # 3 hours

    # 1. Resolve template configuration
    tmpl = get_template_data("mmo")
    assert tmpl is not None
    assert tmpl["positive_count"] == 3

    # 2. Generate Google Calendar web link
    gcal_url = get_google_calendar_url(title, desc, start_ts, end_ts)
    assert "https://www.google.com/calendar/render" in gcal_url
    assert "Guild+Progression+Raid" in gcal_url
    assert "20260915T190000Z" in gcal_url
    assert "20260915T220000Z" in gcal_url

    # 3. Generate ICS batch file content
    event_dict = {
        "event_id": event_id,
        "title": title,
        "description": desc,
        "start_time": start_ts,
        "end_time": end_ts,
        "recurrence_type": "weekly",
    }
    ics_text = generate_ics_batch([event_dict], limit_days=30, max_occurrences=3)
    assert "BEGIN:VCALENDAR" in ics_text
    assert f"SUMMARY:{title}" in ics_text
    assert f"UID:{event_id}_0@discord-event-bot" in ics_text
    assert f"UID:{event_id}_1@discord-event-bot" in ics_text
    assert "END:VCALENDAR" in ics_text

def test_integration_event_reschedule_and_repost_calculation():
    """Integration: Rescheduling recurring event -> recalculating occurrences & repost triggers."""
    base_ts = 1789000000.0 # Initial scheduled start
    conf = {
        "recurrence_type": "daily",
        "repost_trigger": "after_start",
        "repost_offset": "2h",
        "timezone": "UTC",
    }

    # 1. Compute next occurrence
    next_occurrence = compute_next_occurrence(base_ts, conf)
    assert next_occurrence == base_ts + 86400

    # 2. Compute repost timing
    repost_ts = compute_repost_time(base_ts, None, "after_start", "2h", conf)
    assert repost_ts == base_ts + 7200 # 2 hours after start

    # 3. Simulate timeline checks
    event_state = dict(conf, start_time=base_ts)
    
    # Before repost time: Not ready
    ready_early, _, _ = evaluate_repost_readiness(event_state, {}, base_ts + 3600)
    assert ready_early is False

    # After repost time: Ready to spawn next occurrence
    ready_now, next_ts, _ = evaluate_repost_readiness(event_state, {}, base_ts + 7300)
    assert ready_now is True
    assert next_ts == next_occurrence

@pytest.mark.asyncio
async def test_integration_series_resolution_to_batch_cleanup():
    """Integration: Series event resolution -> multi-item matched retrieval -> cleanup pipeline."""
    from services.event_service import resolve_target_events, remove_events_with_cleanup
    from unittest.mock import MagicMock

    ev1 = {"event_id": "EV-SERIES-1", "guild_id": "999", "config_name": "mythic_plus", "channel_id": 111, "message_id": 222}
    ev2 = {"event_id": "EV-SERIES-2", "guild_id": "999", "config_name": "mythic_plus", "channel_id": 111, "message_id": 333}

    with patch("database.get_active_events_by_config", new_callable=AsyncMock) as mock_series:
        mock_series.return_value = [ev1, ev2]
        primary, all_matched, bulk_ids = await resolve_target_events("series:mythic_plus", guild_id=999)
        assert primary == ev1
        assert len(all_matched) == 2
        assert bulk_ids == ["EV-SERIES-1", "EV-SERIES-2"]

    bot = MagicMock()
    bot.get_channel.return_value = None
    with patch("database.delete_active_event", new_callable=AsyncMock) as mock_del:
        removed = await remove_events_with_cleanup(bot, all_matched)
        assert removed == ["EV-SERIES-1", "EV-SERIES-2"]
        assert mock_del.call_count == 2

def test_integration_event_auto_archival_lifecycle():
    """Integration: One-time event finishes -> evaluated by auto-archival -> transitions to closed."""
    now = 1780000000.0
    finished_event = {
        "event_id": "EVT-FIN",
        "status": EventStatus.ACTIVE,
        "recurrence_type": "once",
        "start_time": now - 7200,
        "end_time": now - 1800, # Finished 30 mins ago
        "created_at": now - 10000,
    }

    # Verify auto-archive decision
    assert should_auto_archive_event(finished_event, now) is True

    # Transition to terminal status
    finished_event["status"] = EventStatus.CLOSED
    assert finished_event["status"].is_terminal is True
    assert finished_event["status"].is_interactive is False

@pytest.mark.asyncio
async def test_integration_event_with_multi_reminders_lifecycle():
    """Integration: Normalizing multi-slot reminder offsets -> database storage pipeline."""
    event_payload = {
        "reminder_offsets": ["1d,dm,coming", "2h,ping,all", "15m"],
        "reminder_messages": ["Don't forget tomorrow's raid!", None, "Starting in 15 mins!"],
    }

    # 1. Normalize payload
    slots = normalize_reminders_for_store(event_payload)
    assert len(slots) == 3
    assert slots[0] == {"offset_str": "1d", "method": "dm", "target": "coming", "custom_message": "Don't forget tomorrow's raid!"}
    assert slots[1] == {"offset_str": "2h", "method": "ping", "target": "all", "custom_message": None}
    assert slots[2] == {"offset_str": "15m", "method": "ping", "target": "coming", "custom_message": "Starting in 15 mins!"}

    # 2. Database replace reminders pipeline
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.fetchval = AsyncMock(return_value=3) # 3 pending
    mock_pool.execute = AsyncMock()

    with patch("database.repositories.reminders.get_pool", return_value=mock_pool):
        with patch("database.repositories.reminders.get_event_reminders", return_value=[]):
            await replace_event_reminders("EVT-100", slots)
            assert mock_conn.execute.call_count == 4 # 1 delete + 3 inserts
            mock_pool.execute.assert_called_once()
