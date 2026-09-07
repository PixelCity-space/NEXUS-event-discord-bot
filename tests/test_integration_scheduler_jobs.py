from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.scheduler_task.jobs.lifecycle import (
    handle_event_completion,
    handle_lobby_expiry,
)
from cogs.scheduler_task.jobs.recurring import handle_reposting
from cogs.scheduler_task.jobs.reminders import handle_reminders
from cogs.scheduler_task.jobs.role_cleanup import check_role_cleanup
from utils.enums import EventStatus


@pytest.mark.asyncio
async def test_integration_scheduler_lifecycle_auto_archive():
    """Integration: Scheduler lifecycle job queries archive hours cache and auto-archives finished event after grace period."""
    now = 1780000000.0
    db_event = {
        "event_id": "EVT-LIFE-01",
        "guild_id": "112233",
        "status": EventStatus.ACTIVE,
        "recurrence_type": "once",
        "start_time": now - (8 * 3600), # 8 hours ago
        "end_time": now - (7 * 3600),   # 7 hours ago (beyond 6 hour threshold)
        "created_at": now - (10 * 3600),
        "message_id": 999,
        "channel_id": 888,
    }

    bot = MagicMock()
    bot.get_channel.return_value = None

    with patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting:
        mock_setting.return_value = "6" # 6 hour auto archive
        with patch("database.update_event_status", new_callable=AsyncMock) as mock_status:
            await handle_event_completion(bot, db_event, now)
            mock_status.assert_called_once_with("EVT-LIFE-01", EventStatus.CLOSED)

@pytest.mark.asyncio
async def test_integration_scheduler_lobby_expiry_job():
    """Integration: Scheduler lobby expiry job marks timed-out lobby as LOBBY_EXPIRED."""
    now = 1780000000.0
    expired_lobby = {
        "event_id": "LOBBY-EXP-01",
        "guild_id": "112233",
        "lobby_mode": True,
        "status": EventStatus.ACTIVE,
        "start_time": None,
        "lobby_expires_at": now - 100.0,
        "message_id": 999,
        "channel_id": 888,
    }

    bot = MagicMock()
    bot.get_channel.return_value = None

    with patch("database.update_event_status", new_callable=AsyncMock) as mock_status:
        await handle_lobby_expiry(bot, expired_lobby, now)
        mock_status.assert_called_once_with("LOBBY-EXP-01", EventStatus.LOBBY_EXPIRED)

@pytest.mark.asyncio
async def test_integration_scheduler_recurring_repost_spawn():
    """Integration: Scheduler recurring job closes previous occurrence and spawns new instance."""
    now = 1780000000.0
    db_event = {
        "event_id": "EVT-OLD-1",
        "config_name": "weekly_raid",
        "guild_id": "112233",
        "channel_id": 555666,
        "start_time": now - 80000,
        "recurrence_type": "daily",
        "repost_trigger": "after_start",
        "repost_offset": "1h",
        "recurrence_limit": 5,
        "recurrence_count": 1,
    }

    bot = MagicMock()
    mock_channel = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = 99887766
    mock_channel.send = AsyncMock(return_value=mock_msg)
    bot.get_channel.return_value = mock_channel

    with patch("database.update_event_status", new_callable=AsyncMock) as mock_status:
        with patch("database.create_active_event", new_callable=AsyncMock) as mock_create:
            with patch("database.set_event_message", new_callable=AsyncMock) as mock_msg_set:
                with patch("cogs.scheduler_task.jobs.recurring.load_guild_translations", new_callable=AsyncMock):
                    with patch("cogs.event_ui.DynamicEventView.prepare", new_callable=AsyncMock):
                        with patch("utils.templates.get_event_conf", return_value={"title": "Weekly Raid"}):
                            await handle_reposting(bot, db_event, now)
                            # 1. Old instance closed
                            mock_status.assert_called_once_with("EVT-OLD-1", EventStatus.CLOSED)
                            # 2. New instance created
                            mock_create.assert_called_once()
                            # 3. Message ID updated
                            mock_msg_set.assert_called_once()

@pytest.mark.asyncio
async def test_integration_scheduler_recurring_repost_fetch_channel_fallback():
    """Integration: Scheduler recurring job falls back to fetch_channel when channel is not in cache."""
    now = 1780000000.0
    db_event = {
        "event_id": "EVT-OLD-2",
        "config_name": "weekly_raid",
        "guild_id": "112233",
        "channel_id": 555666,
        "start_time": now - 80000,
        "recurrence_type": "daily",
        "repost_trigger": "after_start",
        "repost_offset": "1h",
        "recurrence_limit": 5,
        "recurrence_count": 1,
    }

    bot = MagicMock()
    mock_channel = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = 11223344
    mock_channel.send = AsyncMock(return_value=mock_msg)
    bot.get_channel.return_value = None
    bot.fetch_channel = AsyncMock(return_value=mock_channel)

    with patch("database.update_event_status", new_callable=AsyncMock), \
         patch("database.create_active_event", new_callable=AsyncMock), \
         patch("database.set_event_message", new_callable=AsyncMock) as mock_msg_set, \
         patch("cogs.scheduler_task.jobs.recurring.load_guild_translations", new_callable=AsyncMock), \
         patch("cogs.event_ui.DynamicEventView.prepare", new_callable=AsyncMock), \
         patch("utils.templates.get_event_conf", return_value={"title": "Weekly Raid"}):

        await handle_reposting(bot, db_event, now)
        bot.fetch_channel.assert_called_once_with(555666)
        mock_msg_set.assert_called_once_with(mock_msg_set.call_args[0][0], 11223344)

@pytest.mark.asyncio
async def test_integration_scheduler_reminders_batch_dispatch():
    """Integration: Scheduler reminders job dispatches due reminder slots and marks them sent."""
    now = 1780000000.0
    start_ts = now + 900 # Starting in 15 mins (15m offset is due)
    db_event = {
        "event_id": "EVT-REM-01",
        "guild_id": "112233",
        "channel_id": 555666,
        "title": "Championship Match",
        "start_time": start_ts,
        "reminder_type": "ping",
        "icon_set": "standard",
    }

    reminders = [
        {"slot_idx": 0, "offset_str": "15m", "method": "ping", "target": "coming", "sent": 0, "custom_message": None}
    ]
    rsvps = [{"user_id": 101, "status": "i_m_coming"}]

    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    with patch("database.get_rsvps", new_callable=AsyncMock) as mock_rsvps:
        mock_rsvps.return_value = rsvps
        with patch("database.mark_reminder_slot_sent", new_callable=AsyncMock) as mock_sent:
            await handle_reminders(bot, db_event, now, preloaded_reminders=reminders)
            mock_channel.send.assert_called_once()
            mock_sent.assert_called_once_with("EVT-REM-01", 0)

@pytest.mark.asyncio
async def test_integration_scheduler_role_cleanup_job():
    """Integration: Scheduler role cleanup job deletes Discord temporary role and clears DB column."""
    now = 1780000000.0
    db_event = {
        "event_id": "EVT-ROLE-01",
        "guild_id": "112233",
        "temp_role_id": 777888,
        "status": EventStatus.CLOSED,
        "start_time": now - 3600,
        "end_time": now - 1800,
    }

    bot = MagicMock()
    guild = MagicMock()
    role = MagicMock()
    role.delete = AsyncMock()
    guild.get_role.return_value = role
    guild.me.guild_permissions.manage_roles = True
    bot.get_guild.return_value = guild

    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()

    with patch("database.repositories.events.get_pool", return_value=mock_pool):
        with patch("database.get_pool", return_value=mock_pool):
            await check_role_cleanup(bot, db_event, now)
            role.delete.assert_called_once()
            mock_pool.execute.assert_called_once()

@pytest.mark.asyncio
async def test_integration_scheduler_role_cleanup_missing_permissions_preserves_db():
    """Integration: When bot lacks Manage Roles permission, role_cleanup does not zero temp_role_id in DB."""
    now = 1780000000.0
    db_event = {
        "event_id": "EVT-ROLE-02",
        "guild_id": "112233",
        "temp_role_id": 777888,
        "status": EventStatus.CLOSED,
        "start_time": now - 3600,
        "end_time": now - 1800,
    }

    bot = MagicMock()
    guild = MagicMock()
    role = MagicMock()
    role.delete = AsyncMock()
    guild.get_role.return_value = role
    guild.me.guild_permissions.manage_roles = False  # Missing permission!
    bot.get_guild.return_value = guild

    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()

    with patch("database.get_pool", return_value=mock_pool):
        await check_role_cleanup(bot, db_event, now)
        role.delete.assert_not_called()
        mock_pool.execute.assert_not_called()  # temp_role_id NOT wiped in DB!

