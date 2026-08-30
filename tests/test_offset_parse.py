import datetime
from utils.offset_parse import parse_offset

def test_parse_offset_minutes():
    """Test duration strings in minutes (e.g. 15m, 45m)."""
    assert parse_offset("15m") == datetime.timedelta(minutes=15)
    assert parse_offset("45M") == datetime.timedelta(minutes=45)
    assert parse_offset(" 30m ") == datetime.timedelta(minutes=30)

def test_parse_offset_hours():
    """Test duration strings in hours (e.g. 2h, 24h)."""
    assert parse_offset("1h") == datetime.timedelta(hours=1)
    assert parse_offset("2H") == datetime.timedelta(hours=2)
    assert parse_offset("24h") == datetime.timedelta(hours=24)

def test_parse_offset_days():
    """Test duration strings in days (e.g. 1d, 7d)."""
    assert parse_offset("1d") == datetime.timedelta(days=1)
    assert parse_offset("7D") == datetime.timedelta(days=7)

def test_parse_offset_invalid_and_fallback():
    """Test fallback to default 1 hour on invalid strings."""
    assert parse_offset("invalid") == datetime.timedelta(hours=1)
    assert parse_offset("") == datetime.timedelta(hours=1)
    assert parse_offset("10s") == datetime.timedelta(hours=1)
    assert parse_offset("-5h") == datetime.timedelta(hours=1)
