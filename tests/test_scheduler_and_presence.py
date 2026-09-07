import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.scheduler_task.cog import SchedulerTask
from cogs.scheduler_task.jobs.role_cleanup import check_role_cleanup
from utils.auth import is_admin, is_master
from utils.presence import (
    _get_cached_presence_config,
    _get_cached_stats,
    run_presence_rotator,
    start_presence_task,
)


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.is_closed = MagicMock(side_effect=[False, True])
    bot.wait_until_ready = AsyncMock()
    bot.change_presence = AsyncMock()
    bot.is_owner = AsyncMock(return_value=False)
    bot.get_guild = MagicMock()
    bot.get_channel = MagicMock()
    return bot

@pytest.mark.asyncio
async def test_scheduler_cog_check_events(mock_bot):
    cog = SchedulerTask(mock_bot)
    cog.check_events.cancel()

    mock_event = {
        "event_id": "EVT-1",
        "guild_id": "123",
        "start_time": time.time() + 3600,
        "end_time": time.time() + 7200,
        "lobby_mode": False,
        "lobby_expires_at": None,
        "reminder_sent": 0,
        "repost_trigger": "after_end",
        "temp_role_id": 9999,
    }

    with patch("database.get_active_events", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_all_active_reminders_batch", new_callable=AsyncMock) as mock_rem_batch, \
         patch("cogs.scheduler_task.cog.handle_lobby_expiry", new_callable=AsyncMock) as mock_lobby, \
         patch("cogs.scheduler_task.cog.handle_reminders", new_callable=AsyncMock) as mock_rem, \
         patch("cogs.scheduler_task.cog.check_role_cleanup", new_callable=AsyncMock) as mock_cleanup, \
         patch("cogs.scheduler_task.cog.handle_reposting", new_callable=AsyncMock) as mock_repost, \
         patch("cogs.scheduler_task.cog.handle_event_completion", new_callable=AsyncMock) as mock_complete:

        mock_get_ev.return_value = [mock_event]
        mock_rem_batch.return_value = {"EVT-1": []}

        await cog.check_events.coro(cog)

        mock_lobby.assert_called_once()
        mock_rem.assert_called_once()
        mock_cleanup.assert_called_once()
        mock_repost.assert_called_once()
        mock_complete.assert_called_once()

    cog.cog_unload()

@pytest.mark.asyncio
async def test_role_cleanup_job(mock_bot):
    guild = MagicMock()
    guild.me.guild_permissions.manage_roles = True
    role = MagicMock()
    guild.get_role.return_value = role
    role.delete = AsyncMock()
    mock_bot.get_guild.return_value = guild

    db_event = {
        "event_id": "EVT-OLD",
        "guild_id": "123",
        "start_time": time.time() - 7200,
        "end_time": time.time() - 3600,
        "temp_role_id": 8888,
        "temp_role_cleaned": 0,
        "status": "active",
    }

    mock_pool = MagicMock()
    mock_pool.execute = AsyncMock()

    with patch("database.get_pool", new_callable=AsyncMock) as mock_gp:
        mock_gp.return_value = mock_pool
        await check_role_cleanup(mock_bot, db_event, time.time())
        role.delete.assert_called_once()
        mock_pool.execute.assert_called_once()

@pytest.mark.asyncio
async def test_presence_rotator_lifecycle(mock_bot):
    with patch("database.get_global_stats", new_callable=AsyncMock) as mock_stats, \
         patch("database.get_global_setting", new_callable=AsyncMock) as mock_setting, \
         patch("asyncio.sleep", new_callable=AsyncMock):

        mock_stats.return_value = {"guilds": 10, "events": 25, "rsvps": 100}
        mock_setting.return_value = '{"time": 15, "mode": "sequential", "statuses": [{"id": "s1", "type": "watching", "text": "{event_count} events in {guild_count} guilds"}]}'

        import utils.presence
        utils.presence._stats_cache = {"data": {}, "expires_at": 0.0}
        utils.presence._config_cache = {"data": None, "expires_at": 0.0}

        stats = await _get_cached_stats()
        assert stats["events"] == 25

        config = await _get_cached_presence_config()
        assert config["mode"] == "sequential"

        await run_presence_rotator(mock_bot)
        mock_bot.change_presence.assert_called()

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_task = MagicMock()
            def fake_create_task(coro):
                coro.close()
                return mock_task
            mock_loop.return_value.create_task = MagicMock(side_effect=fake_create_task)
            mock_bot.loop = mock_loop.return_value
            task = start_presence_task(mock_bot)
            assert task is not None

@pytest.mark.asyncio
async def test_auth_is_admin_all_scenarios(mock_bot):
    # 1. Bot Owner bypass
    mock_bot.is_owner.return_value = True
    inter = MagicMock(spec=discord.Interaction)
    inter.client = mock_bot
    inter.user = MagicMock()
    inter.guild_id = 123
    inter.channel_id = 456
    assert await is_admin(inter) is True

    # 2. Context with Administrator permissions
    mock_bot.is_owner.return_value = False
    ctx = MagicMock(spec=commands.Context)
    ctx.bot = mock_bot
    ctx.author = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 123
    ctx.channel = MagicMock()
    ctx.channel.id = 456
    ctx.author.guild_permissions = MagicMock()
    ctx.author.guild_permissions.administrator = True

    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings:
        mock_settings.return_value = {}
        assert await is_admin(ctx) is True

    # 3. Explicit Admin Roles
    ctx.author.guild_permissions.administrator = False
    mock_role = MagicMock()
    mock_role.id = 777
    ctx.author.roles = [mock_role]

    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings:
        mock_settings.return_value = {"admin_role_ids": "777,888"}
        assert await is_admin(ctx) is True

    # 4. Strict channel mismatch
    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings:
        mock_settings.return_value = {"admin_channel_ids": "999"}
        assert await is_admin(ctx) is False

@pytest.mark.asyncio
async def test_auth_is_master(mock_bot):
    inter = MagicMock(spec=discord.Interaction)
    inter.client = mock_bot
    inter.user = MagicMock()
    inter.user.guild_permissions = MagicMock()
    inter.user.guild_permissions.administrator = True
    inter.guild_id = 99999

    # Owner true
    mock_bot.is_owner.return_value = True
    assert await is_master(inter) is True

    # Master guild check
    mock_bot.is_owner.return_value = False
    with patch("utils.auth.config") as mock_cfg, \
         patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings:
        mock_settings.return_value = {}
        mock_cfg.master_guild_ids = [99999]
        assert await is_master(inter) is True

        mock_cfg.master_guild_ids = [11111]
        assert await is_master(inter) is False
