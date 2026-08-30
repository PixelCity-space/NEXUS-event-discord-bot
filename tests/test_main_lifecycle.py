import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord import app_commands
import main
from main import EventBot

@pytest.fixture
def bot_instance():
    with patch("main.config._data", {"command_prefix": "!", "master_guild_ids": [123456]}):
        bot = EventBot()
        bot.db_manager = MagicMock()
        bot.db_manager.close = AsyncMock()
        return bot

@pytest.mark.asyncio
async def test_main_init_database_missing_url(bot_instance):
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            await bot_instance._init_database()

@pytest.mark.asyncio
async def test_main_init_database_success_and_seeding(bot_instance):
    mock_pool = MagicMock()
    bot_instance.master_guild_ids = [123456]
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}), \
         patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool, \
         patch("database.set_pool", new_callable=AsyncMock) as mock_set_pool, \
         patch("database.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("main.load_guild_translations", new_callable=AsyncMock) as mock_trans, \
         patch("database.get_all_global_emoji_sets", new_callable=AsyncMock) as mock_get_sets, \
         patch("database.save_global_emoji_set", new_callable=AsyncMock) as mock_save_set:

        mock_create_pool.return_value = mock_pool
        mock_get_sets.return_value = []  # Triggers seeding factory defaults

        await bot_instance._init_database()
        assert bot_instance.db_pool == mock_pool
        mock_init_db.assert_called_once()
        mock_trans.assert_called_once_with(123456)
        assert mock_save_set.call_count > 0

@pytest.mark.asyncio
async def test_main_init_database_exception_handling(bot_instance):
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://invalid"}), \
         patch("asyncpg.create_pool", side_effect=Exception("Connection refused")):
        with pytest.raises(RuntimeError, match="Failed to initialize database"):
            await bot_instance._init_database()

@pytest.mark.asyncio
async def test_main_load_extensions(bot_instance):
    bot_instance.load_extension = AsyncMock()
    bot_instance.master_guild_ids = [123456]
    mock_cog = MagicMock()
    bot_instance.get_cog = MagicMock(return_value=mock_cog)
    bot_instance.tree.remove_command = MagicMock()
    bot_instance.tree.add_command = MagicMock()

    await bot_instance._load_extensions()
    assert bot_instance.load_extension.call_count >= 6
    bot_instance.tree.remove_command.assert_called_with("master")
    bot_instance.tree.add_command.assert_called_once()

@pytest.mark.asyncio
async def test_main_load_extensions_errors_handled(bot_instance):
    bot_instance.load_extension = AsyncMock(side_effect=Exception("Cog load failed"))
    bot_instance.master_guild_ids = []
    # Should log errors without raising unhandled exception
    await bot_instance._load_extensions()

@pytest.mark.asyncio
async def test_main_load_persistent_views(bot_instance):
    active_events = [
        {"event_id": "EVT-1", "config_name": "manual", "guild_id": 123456},
        {"event_id": "EVT-ERR", "config_name": "manual", "guild_id": 123456},
    ]
    bot_instance.add_view = MagicMock()

    async def mock_prepare_side_effect():
        pass

    with patch("main.load_custom_sets", new_callable=AsyncMock) as mock_load_sets, \
         patch("database.get_active_events", new_callable=AsyncMock) as mock_get_evs, \
         patch("main.DynamicEventView.prepare", new_callable=AsyncMock) as mock_prep:

        mock_get_evs.return_value = active_events

        await bot_instance._load_persistent_views()
        mock_load_sets.assert_called_once()
        assert bot_instance.add_view.call_count == 2

@pytest.mark.asyncio
async def test_main_error_handler_check_failure(bot_instance):
    bot_instance._register_error_handler()

    handler = bot_instance.tree.on_error

    # Case 1: is_done = False
    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 123456
    inter.response = MagicMock()
    inter.response.is_done.return_value = False
    inter.response.send_message = AsyncMock()

    error = app_commands.CheckFailure()
    await handler(inter, error)
    inter.response.send_message.assert_called_once()

    # Case 2: is_done = True
    inter2 = MagicMock(spec=discord.Interaction)
    inter2.guild_id = 123456
    inter2.response = MagicMock()
    inter2.response.is_done.return_value = True
    inter2.followup = MagicMock()
    inter2.followup.send = AsyncMock()

    await handler(inter2, error)
    inter2.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_main_error_handler_general_exception(bot_instance):
    bot_instance._register_error_handler()
    handler = bot_instance.tree.on_error

    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 123456
    inter.response = MagicMock()
    inter.response.is_done.return_value = True
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()

    error = app_commands.AppCommandError("Unexpected failure")
    await handler(inter, error)
    inter.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_main_setup_hook_and_lifecycle(bot_instance):
    bot_instance._init_database = AsyncMock()
    bot_instance._load_extensions = AsyncMock()
    bot_instance._load_persistent_views = AsyncMock()
    bot_instance._register_error_handler = MagicMock()

    with patch("main.start_presence_task") as mock_presence, \
         patch("main.set_log_level") as mock_set_log:

        await bot_instance.setup_hook()
        bot_instance._init_database.assert_called_once()
        bot_instance._load_extensions.assert_called_once()
        bot_instance._load_persistent_views.assert_called_once()
        mock_presence.assert_called_once_with(bot_instance)

    # Test on_ready
    mock_user = MagicMock()
    mock_user.id = 1000
    mock_user.__str__.return_value = "EventBot#0001"
    bot_instance._connection.user = mock_user
    await bot_instance.on_ready()

    # Test close
    with patch("discord.ext.commands.Bot.close", new_callable=AsyncMock) as mock_super_close:
        await bot_instance.close()
        bot_instance.db_manager.close.assert_called_once()
        mock_super_close.assert_called_once()
