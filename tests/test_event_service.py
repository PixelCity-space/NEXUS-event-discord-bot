import pytest
from unittest.mock import AsyncMock, patch
from discord import app_commands
from services.event_service import (
    resolve_target_events,
    search_events_autocomplete,
    update_event_time_parsed,
)

@pytest.mark.asyncio
async def test_resolve_target_events_single_event():
    """Test resolving a single event by event_id."""
    sample_event = {"event_id": "EVT-101", "title": "Friday Raid", "guild_id": "123"}
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = sample_event
        primary, all_matched, bulk_ids = await resolve_target_events("EVT-101", guild_id=123)
        assert primary == sample_event
        assert len(all_matched) == 1
        assert bulk_ids is None

@pytest.mark.asyncio
async def test_resolve_target_events_series_bulk():
    """Test resolving a series without occurrence returns root and bulk IDs."""
    ev1 = {"event_id": "EVT-SERIES-1", "title": "Weekly Raid #1", "config_name": "weekly_raid"}
    ev2 = {"event_id": "EVT-SERIES-2", "title": "Weekly Raid #2", "config_name": "weekly_raid"}
    with patch("database.get_active_events_by_config", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = [ev1, ev2]
        primary, all_matched, bulk_ids = await resolve_target_events("series:weekly_raid", guild_id=123)
        assert primary == ev1
        assert len(all_matched) == 2
        assert bulk_ids == ["EVT-SERIES-1", "EVT-SERIES-2"]

@pytest.mark.asyncio
async def test_resolve_target_events_series_occurrence():
    """Test resolving a specific occurrence index of a series."""
    ev1 = {"event_id": "EVT-SERIES-1", "title": "Weekly Raid #1", "config_name": "weekly_raid"}
    ev2 = {"event_id": "EVT-SERIES-2", "title": "Weekly Raid #2", "config_name": "weekly_raid"}
    with patch("database.get_active_events_by_config", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = [ev1, ev2]
        primary, all_matched, bulk_ids = await resolve_target_events("series:weekly_raid", guild_id=123, occurrence=2)
        assert primary == ev2
        assert bulk_ids is None

@pytest.mark.asyncio
async def test_search_events_autocomplete_filtering():
    """Test autocomplete search filters results by title and query string."""
    events = [
        {"event_id": "EV-001", "title": "Mythic Dungeon", "config_name": "manual"},
        {"event_id": "EV-002", "title": "PvP Arena", "config_name": "manual"},
    ]
    with patch("database.get_active_events", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = events
        choices = await search_events_autocomplete(guild_id=123, current="dungeon")
        assert len(choices) == 1
        assert choices[0].value == "EV-001"

@pytest.mark.asyncio
async def test_update_event_time_parsed():
    """Test parsing standard date strings into timestamp and updating DB."""
    with patch("database.update_event_time", new_callable=AsyncMock) as mock_update:
        ts = await update_event_time_parsed("EVT-100", "2026-10-15 20:00:00")
        assert isinstance(ts, float)
        mock_update.assert_called_once_with("EVT-100", ts)
