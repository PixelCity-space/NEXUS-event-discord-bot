import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from database.repositories.drafts import save_draft, get_draft, delete_draft
from database.repositories.settings import (
    save_guild_setting,
    get_guild_setting,
    get_all_guild_settings,
    save_guild_translation,
    get_guild_translations,
    delete_guild_translation,
)
from database.repositories.emojis import save_emoji_set, get_all_custom_emoji_sets
from utils.templates import load_custom_sets, get_active_set

@pytest.mark.asyncio
async def test_integration_event_draft_save_and_load():
    """Integration: Saving, loading, and serializing draft event configuration."""
    mock_pool = MagicMock()
    draft_payload = {"title": "Draft Raid", "color": "0xFF0000", "max_accepted": 10}
    mock_row = {
        "draft_id": "DRAFT-123",
        "creator_id": "999",
        "title": "Draft Raid",
        "data": json.dumps(draft_payload),
        "guild_id": "112233",
    }
    mock_pool.fetchrow = AsyncMock(return_value=mock_row)
    mock_pool.execute = AsyncMock()

    with patch("database.repositories.drafts.get_pool", return_value=mock_pool):
        # 1. Save draft
        await save_draft("112233", "DRAFT-123", "999", "Draft Raid", draft_payload)
        mock_pool.execute.assert_called_once()

        # 2. Retrieve draft
        retrieved = await get_draft("DRAFT-123", "112233")
        assert retrieved is not None
        assert retrieved["title"] == "Draft Raid"

        # 3. Delete draft
        await delete_draft("DRAFT-123", "112233")
        assert mock_pool.execute.call_count == 2

@pytest.mark.asyncio
async def test_integration_guild_settings_upsert_and_retrieve():
    """Integration: Setting guild configuration key-values and retrieving settings map."""
    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value={"value": "hu"})
    mock_pool.fetch = AsyncMock(return_value=[{"key": "language", "value": "hu"}, {"key": "auto_archive_hours", "value": "24"}])

    with patch("database.repositories.settings.get_pool", return_value=mock_pool):
        # 1. Save setting
        await save_guild_setting("112233", "language", "hu")
        mock_pool.execute.assert_called_once()

        # 2. Get single setting
        val = await get_guild_setting("112233", "language")
        assert val == "hu"

        # 3. Get all settings map
        all_settings = await get_all_guild_settings("112233")
        assert all_settings == {"language": "hu", "auto_archive_hours": "24"}

@pytest.mark.asyncio
async def test_integration_guild_translations_override_and_clear():
    """Integration: Managing guild-specific i18n translation string overrides."""
    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()
    mock_pool.fetch = AsyncMock(return_value=[{"key": "BTN_ACCEPT", "value": "Csatlakozom!"}])

    with patch("database.repositories.settings.get_pool", return_value=mock_pool):
        # 1. Save translation override
        await save_guild_translation("112233", "BTN_ACCEPT", "Csatlakozom!")
        mock_pool.execute.assert_called_once()

        # 2. Get translations
        trans = await get_guild_translations("112233")
        assert trans == {"BTN_ACCEPT": "Csatlakozom!"}

        # 3. Delete translation override
        await delete_guild_translation("112233", "BTN_ACCEPT")
        assert mock_pool.execute.call_count == 2

@pytest.mark.asyncio
async def test_integration_custom_emoji_set_save_and_cache():
    """Integration: Saving custom emoji set to database and loading into in-memory template cache."""
    custom_set_data = {
        "options": [{"id": "knight", "label": "Knight", "emoji": "⚔️", "positive": True}],
        "positive_count": 1,
    }
    mock_db_sets = [
        {"set_id": "custom_rpg", "name": "RPG Set", "data": json.dumps(custom_set_data)}
    ]

    with patch("database.get_all_global_emoji_sets", new_callable=AsyncMock, return_value=[]):
        with patch("database.get_all_custom_emoji_sets", new_callable=AsyncMock, return_value=mock_db_sets):
            # Load into memory cache
            await load_custom_sets()

            # Retrieve via get_active_set
            active = get_active_set("custom_rpg")
            assert active is not None
            assert len(active["options"]) == 1
            assert active["options"][0]["id"] == "knight"
            assert active["options"][0]["emoji"] == "⚔️"

@pytest.mark.asyncio
async def test_integration_event_creation_and_atomic_deletion():
    """Integration: Atomic deletion cleans up event_reminders, rsvps, and active_events in a single transaction."""
    from database.repositories.events import delete_active_event

    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock()
    mock_conn.transaction.return_value.__aexit__ = AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("database.repositories.events.get_pool", return_value=mock_pool):
        await delete_active_event("EVT-100", guild_id="112233")
        # Verify 3 DELETE statements executed inside transaction: reminders, rsvps, active_events
        assert mock_conn.execute.call_count == 3
