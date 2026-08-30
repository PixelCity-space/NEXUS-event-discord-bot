import datetime
from utils.calendar_utils import (
    format_ts_utc,
    get_google_calendar_url,
    get_outlook_calendar_url,
    get_yahoo_calendar_url,
    generate_ics_batch,
)
from utils.enums import EventStatus, AttendanceStatus, RecurrenceType
from utils.tiers import SubscriptionTier

def test_format_ts_utc():
    """Test converting timestamp to standard UTC format (YYYYMMDDTHHMMSSZ)."""
    # 2026-01-01 12:00:00 UTC = timestamp 1767268800
    ts = 1767268800
    formatted = format_ts_utc(ts)
    assert formatted == "20260101T120000Z"

def test_get_google_calendar_url():
    """Test generating Google Calendar template URL with encoded query parameters."""
    start_ts = 1767268800
    url = get_google_calendar_url("Raid Night", "Bring consumables", start_ts)
    assert "https://www.google.com/calendar/render?action=TEMPLATE" in url
    assert "text=Raid+Night" in url
    assert "dates=20260101T120000Z" in url

def test_get_outlook_calendar_url():
    """Test generating Outlook calendar web compose URL."""
    start_ts = 1767268800
    url = get_outlook_calendar_url("Boss Fight", "Discord Voice #1", start_ts)
    assert "outlook.live.com/calendar" in url
    assert "subject=Boss+Fight" in url
    assert "startdt=" in url

def test_get_yahoo_calendar_url():
    """Test generating Yahoo calendar URL."""
    start_ts = 1767268800
    url = get_yahoo_calendar_url("Community Meetup", "Welcome everyone", start_ts)
    assert "calendar.yahoo.com" in url
    assert "title=Community+Meetup" in url
    assert "st=20260101T120000Z" in url

def test_generate_ics_batch():
    """Test batch ICS generation output formatting."""
    events = [
        {
            "event_id": "EV-999",
            "title": "Tournament Finals",
            "description": "Grand finals match",
            "start_time": 1767268800,
            "end_time": 1767276000,
            "recurrence_type": "once",
        }
    ]
    ics_text = generate_ics_batch(events)
    assert "BEGIN:VCALENDAR" in ics_text
    assert "BEGIN:VEVENT" in ics_text
    assert "SUMMARY:Tournament Finals" in ics_text
    assert "UID:EV-999_0@discord-event-bot" in ics_text
    assert "END:VEVENT" in ics_text
    assert "END:VCALENDAR" in ics_text

def test_event_status_interactive_and_terminal():
    """Test EventStatus enum properties for interactive and terminal states."""
    # Interactive states
    assert EventStatus.ACTIVE.is_interactive is True
    assert EventStatus.RESCHEDULED.is_interactive is True
    assert EventStatus.CANCELLED.is_interactive is False
    assert EventStatus.CLOSED.is_interactive is False

    # Terminal states
    assert EventStatus.CANCELLED.is_terminal is True
    assert EventStatus.DELETED.is_terminal is True
    assert EventStatus.CLOSED.is_terminal is True
    assert EventStatus.ENDED.is_terminal is True
    assert EventStatus.LOBBY_EXPIRED.is_terminal is True
    assert EventStatus.ACTIVE.is_terminal is False

def test_subscription_tiers_enum():
    """Test SubscriptionTier enum integer ordering and comparisons."""
    assert SubscriptionTier.STANDARD < SubscriptionTier.PREMIUM
    assert SubscriptionTier.PREMIUM < SubscriptionTier.MASTER
    assert SubscriptionTier.MASTER == 2
