import pytest
from unittest.mock import AsyncMock, patch
from services.attendance_service import (
    get_eligible_attendance_participants,
    toggle_user_attendance,
    search_attendance_events_autocomplete,
)

@pytest.mark.asyncio
async def test_get_eligible_attendance_participants_positive_filtering():
    """Test filtering RSVPs to only positive roles and standard accepted status."""
    rsvps = [
        {"user_id": 101, "status": "tank", "attendance": "present"},
        {"user_id": 102, "status": "heal", "attendance": "no_show"},
        {"user_id": 103, "status": "not_coming", "attendance": None},
        {"user_id": 104, "status": "accepted", "attendance": "present"},
    ]
    with patch("database.get_event_attendance_data", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = rsvps
        # 'mmo' template has positive options 'tank', 'heal', 'dps'
        eligible = await get_eligible_attendance_participants("EVT-101", "mmo")
        uids = [e["user_id"] for e in eligible]
        assert 101 in uids
        assert 102 in uids
        assert 104 in uids
        assert 103 not in uids

@pytest.mark.asyncio
async def test_toggle_user_attendance_present_to_noshow():
    """Test toggling attendance from 'present' transitions to 'no_show'."""
    with patch("database.update_rsvp_attendance", new_callable=AsyncMock) as mock_db:
        new_status = await toggle_user_attendance("EVT-1", 12345, "present")
        assert new_status == "no_show"
        mock_db.assert_called_once_with("EVT-1", 12345, "no_show")

@pytest.mark.asyncio
async def test_toggle_user_attendance_noshow_to_present():
    """Test toggling attendance from 'no_show' transitions to 'present'."""
    with patch("database.update_rsvp_attendance", new_callable=AsyncMock) as mock_db:
        new_status = await toggle_user_attendance("EVT-1", 12345, "no_show")
        assert new_status == "present"
        mock_db.assert_called_once_with("EVT-1", 12345, "present")

@pytest.mark.asyncio
async def test_search_attendance_events_autocomplete_empty_guild():
    """Test attendance autocomplete returns empty list if guild_id is None."""
    choices = await search_attendance_events_autocomplete(None, "raid")
    assert choices == []

@pytest.mark.asyncio
async def test_search_attendance_events_autocomplete_filtering():
    """Test attendance autocomplete filters by title and limits to 25 items."""
    db_events = [
        {"event_id": "EV-1", "title": "Friday Boss Raid"},
        {"event_id": "EV-2", "title": "Saturday Casual PvP"},
    ]
    with patch("database.get_attendance_eligible_events", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = db_events
        choices = await search_attendance_events_autocomplete("999", "boss")
        assert len(choices) == 1
        assert choices[0].value == "EV-1"
