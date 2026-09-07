import time
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

import database
from database.connection import DatabaseManager
from database.repositories import drafts as draft_repo
from database.repositories import emojis as emoji_repo
from database.repositories import events as event_repo
from database.repositories import reminders as reminder_repo
from database.repositories import rsvps as rsvp_repo
from database.repositories import settings as settings_repo


@pytest.fixture
def mock_pool():
    pool = MagicMock(spec=asyncpg.Pool)
    conn = MagicMock(spec=asyncpg.Connection)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    
    class AcquireContext:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class TxContext:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    pool.acquire.return_value = AcquireContext()
    conn.transaction.return_value = TxContext()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetchval = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool, conn

@pytest.mark.asyncio
async def test_database_manager_lifecycle(mock_pool):
    pool, conn = mock_pool
    mgr = DatabaseManager()
    assert not mgr.is_initialized
    with pytest.raises(RuntimeError):
        mgr.get_pool()

    mgr.set_pool(pool)
    assert mgr.is_initialized
    assert mgr.get_pool() == pool

    async with mgr.acquire() as c:
        assert c == conn

    await mgr.close()
    assert not mgr.is_initialized
    pool.close.assert_called_once()

@pytest.mark.asyncio
async def test_database_manager_run_migrations(mock_pool, tmp_path):
    pool, conn = mock_pool
    mgr = DatabaseManager(pool)

    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_initial.sql").write_text("CREATE TABLE test_tbl (id INT);", encoding="utf-8")
    (mig_dir / "002_add_col.sql").write_text("ALTER TABLE test_tbl ADD col INT;", encoding="utf-8")

    conn.fetch.return_value = [{"version": 1}]

    with patch("database.connection.MIGRATIONS_DIR", mig_dir):
        await mgr.run_migrations(conn)
        assert conn.execute.call_count >= 3

    with patch("database.connection.MIGRATIONS_DIR", tmp_path / "non_existent"):
        await mgr.run_migrations(conn)

@pytest.mark.asyncio
async def test_events_repository_crud(mock_pool):
    pool, conn = mock_pool
    database.db_manager.set_pool(pool)

    # 1. check_config_exists
    pool.fetchrow.return_value = {"1": 1}
    assert await event_repo.check_config_exists("123", "raid") is True

    # 2. create_active_event
    event_data = {
        "title": "Raid Night",
        "description": "Weekly raid",
        "start_time": time.time(),
        "end_time": time.time() + 7200,
        "image_urls": ["https://example.com/1.png", "https://example.com/2.png"],
        "ping_role": "<@&12345>",
        "reminder_offsets": ["1h", "30m"],
        "rsvp_allowed_role_ids": "111,222",
        "lobby_mode": False,
    }
    with patch("database.repositories.events.replace_event_reminders", new_callable=AsyncMock) as mock_replace_rem:
        eid = await event_repo.create_active_event(
            guild_id="123",
            event_id="EVT-100",
            config_name="raid",
            channel_id=456,
            start_time=event_data["start_time"],
            data=event_data,
        )
        assert eid == "EVT-100"
        pool.execute.assert_called()
        mock_replace_rem.assert_called_once()

    # 3. get_active_events & get_active_event
    pool.fetch.return_value = [{"event_id": "EVT-100", "title": "Raid Night"}]
    events = await event_repo.get_active_events("123", include_all=True)
    assert len(events) == 1

    events_no_guild = await event_repo.get_active_events(None, include_all=False)
    assert len(events_no_guild) == 1

    pool.fetchrow.return_value = {"event_id": "EVT-100", "title": "Raid Night"}
    ev = await event_repo.get_active_event("EVT-100", "123")
    assert ev["event_id"] == "EVT-100"

    # 4. update_active_event
    pool.fetchrow.return_value = {
        "reminder_message": "Don't be late!",
        "rsvp_allowed_role_ids": "111,222",
        "lobby_mode": False,
        "lobby_expires_at": None,
        "lobby_remind_on_fill": True,
    }
    with patch("database.repositories.events.replace_event_reminders", new_callable=AsyncMock):
        await event_repo.update_active_event("EVT-100", event_data)
        assert pool.execute.call_count >= 2

    # 5. update_event_status & update_event_status_bulk
    await event_repo.update_event_status("EVT-100", "cancelled")
    await event_repo.update_event_status_bulk(["EVT-100", "EVT-101"], "cancelled")

    # 6. delete_active_event
    await event_repo.delete_active_event("EVT-100")

    # 7. set_event_message & set_lobby_start_time & update_event_time
    await event_repo.set_event_message("EVT-100", 999999)
    await event_repo.set_lobby_start_time("EVT-100", time.time())
    await event_repo.update_event_time("EVT-100", time.time())

@pytest.mark.asyncio
async def test_emojis_repository_crud(mock_pool):
    pool, conn = mock_pool
    database.db_manager.set_pool(pool)

    # Global emoji sets
    pool.fetch.return_value = [{"set_id": "standard", "name": "Standard", "data": "{}"}]
    sets = await emoji_repo.get_all_global_emoji_sets()
    assert len(sets) == 1

    await emoji_repo.save_global_emoji_set("standard", "Standard", {"options": []})
    await emoji_repo.delete_global_emoji_set("standard")
    await emoji_repo.clear_global_emoji_sets()

    # Guild custom emoji sets
    pool.fetch.return_value = [{"set_id": "custom1", "data": "{}"}]
    guild_sets = await emoji_repo.get_emoji_sets("123")
    assert len(guild_sets) == 1

    all_custom = await emoji_repo.get_all_custom_emoji_sets()
    assert len(all_custom) == 1

    await emoji_repo.save_emoji_set("123", "custom1", "Custom 1", {"options": []})
    await emoji_repo.delete_emoji_set("123", "custom1")

@pytest.mark.asyncio
async def test_settings_repository_crud(mock_pool):
    pool, conn = mock_pool
    database.db_manager.set_pool(pool)

    pool.fetchrow.return_value = {"value": "hu"}
    val = await settings_repo.get_guild_setting("123", "language", default="en")
    assert val == "hu"

    pool.fetchrow.return_value = None
    val_def = await settings_repo.get_guild_setting("123", "timezone", default="UTC")
    assert val_def == "UTC"

    await settings_repo.save_guild_setting("123", "language", "hu")

    pool.fetch.return_value = [{"key": "lang", "value": "en"}, {"key": "tz", "value": "UTC"}]
    all_settings = await settings_repo.get_all_guild_settings("123")
    assert all_settings["lang"] == "en"

    # Global settings
    await settings_repo.save_global_setting("maintenance", "0")
    pool.fetchrow.return_value = {"value": "0"}
    g_val = await settings_repo.get_global_setting("maintenance")
    assert g_val == "0"

    # Translations
    await settings_repo.save_guild_translation("123", "TITLE", "Cím")
    pool.fetch.return_value = [{"key": "TITLE", "value": "Cím"}]
    trans = await settings_repo.get_guild_translations("123")
    assert trans["TITLE"] == "Cím"
    await settings_repo.delete_guild_translation("123", "TITLE")

    # Reset & stats
    await settings_repo.reset_guild_data("123")
    pool.fetchval.side_effect = [5, 20, 100]
    stats = await settings_repo.get_global_stats()
    assert stats["guilds"] == 5
    assert stats["events"] == 20
    assert stats["rsvps"] == 100

@pytest.mark.asyncio
async def test_reminders_and_drafts_repository(mock_pool):
    pool, conn = mock_pool
    database.db_manager.set_pool(pool)

    # Reminders
    rems = reminder_repo.normalize_reminders_for_store({"reminder_offsets": ["30m", "1h"]})
    assert len(rems) == 2

    msg = reminder_repo.normalize_reminder_message_for_store({"reminder_message": "Event is starting!"})
    assert msg == "Event is starting!"

    pool.fetch.return_value = [{"event_id": "EVT-1", "slot_idx": 0, "offset_str": "1h", "sent": 0}]
    ev_rems = await reminder_repo.get_event_reminders("EVT-1")
    assert len(ev_rems) == 1

    batch_map = await reminder_repo.get_all_active_reminders_batch()
    assert "EVT-1" in batch_map

    await reminder_repo.replace_event_reminders("EVT-1", rems)
    await reminder_repo.mark_reminder_slot_sent("EVT-1", 0)
    await reminder_repo.mark_all_reminder_slots_sent("EVT-1")
    await reminder_repo.mark_reminder_sent("EVT-1", "123")

    # Drafts
    await draft_repo.save_draft("123", "DRAFT-1", "999", "Draft Raid", {"title": "Draft Raid"})
    pool.fetchrow.return_value = {"draft_id": "DRAFT-1", "title": "Draft Raid"}
    d = await draft_repo.get_draft("DRAFT-1", "123")
    assert d["title"] == "Draft Raid"

    pool.fetch.return_value = [{"draft_id": "DRAFT-1", "title": "Draft Raid"}]
    user_drafts = await draft_repo.get_user_drafts("123", "999")
    assert len(user_drafts) == 1

    await draft_repo.delete_draft("DRAFT-1", "123")
    await draft_repo.delete_all_user_drafts("123", "999")

@pytest.mark.asyncio
async def test_rsvps_repository_crud(mock_pool):
    pool, conn = mock_pool
    database.db_manager.set_pool(pool)

    pool.fetch.return_value = [{"user_id": 101, "status": "accepted"}]
    rsvps = await rsvp_repo.get_rsvps("EVT-1")
    assert len(rsvps) == 1

    await rsvp_repo.update_rsvp("EVT-1", 101, "accepted")
    await rsvp_repo.get_rsvps_with_time("EVT-1")

    # promote_next_waiting
    pool.fetchrow.return_value = {"user_id": 102}
    promoted_uid = await rsvp_repo.promote_next_waiting("EVT-1", "wait_tank", "tank")
    assert promoted_uid == 102

    # attendance helpers
    await rsvp_repo.get_attendance_eligible_events("123")
    await rsvp_repo.get_event_attendance_data("EVT-1")
    await rsvp_repo.update_rsvp_attendance("EVT-1", 101, "present")
    await rsvp_repo.get_guild_reliability_stats("123", all_time=True)
    await rsvp_repo.get_event_reliability_audit("EVT-1", "123")
    await rsvp_repo.get_guild_rsvps_export("123")
