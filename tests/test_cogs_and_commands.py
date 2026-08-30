import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord.ext import commands
from cogs.server_setup.cog import ServerSetupCog
from cogs.event_commands.cogs.event_cog import EventCommands
from cogs.event_commands.cogs.admin_cog import AdminCommands
from cogs.event_commands.cogs.draft_cog import DraftCommands
from cogs.attendance import AttendanceCog, AttendanceView
from cogs.emoji_wizard import EmojiWizardView, TemplateChoiceView, ConfirmDeleteView
from cogs.message_wizard import MessageWizardView, MessageEditModal
from cogs.master_commands import MasterCommands, MasterPresenceView
from cogs.event_commands.views.my_events import MyEventsView
from cogs.event_commands.views.history import EventHistoryView

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 12345678
    bot.is_owner = AsyncMock(return_value=True)
    bot.get_guild = MagicMock()
    bot.get_channel = MagicMock()
    bot.guilds = [MagicMock()]
    bot.latency = 0.045
    return bot

@pytest.fixture
def mock_interaction(mock_bot):
    inter = MagicMock(spec=discord.Interaction)
    inter.client = mock_bot
    inter.guild_id = 12345
    inter.channel_id = 67890
    inter.user = MagicMock(spec=discord.Member)
    inter.user.id = 999
    inter.response = MagicMock()
    inter.response.defer = AsyncMock()
    inter.response.send_modal = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_server_setup_cog(mock_bot, mock_interaction):
    cog = ServerSetupCog(mock_bot)
    with patch("cogs.server_setup.cog.load_guild_translations", new_callable=AsyncMock), \
         patch("cogs.server_setup.cog.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("cogs.server_setup.cog.ServerSetupView.prepare", new_callable=AsyncMock):

        mock_admin.return_value = True
        await cog.admin_setup.callback(cog, mock_interaction)
        mock_interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_event_commands_list_and_sheets(mock_bot, mock_interaction):
    cog = EventCommands(mock_bot)
    mock_event = {
        "event_id": "EVT-TEST",
        "title": "Raid Night",
        "start_time": time.time() + 3600,
        "config_name": "manual",
        "created_at": time.time(),
    }

    with patch("utils.auth.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("utils.i18n.load_guild_translations", new_callable=AsyncMock), \
         patch("cogs.event_commands.cogs.event_cog.load_guild_translations", new_callable=AsyncMock), \
         patch("database.get_active_events", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_guild_events_export", new_callable=AsyncMock) as mock_events_exp, \
         patch("database.get_guild_rsvps_export", new_callable=AsyncMock) as mock_rsvps_exp:

        mock_admin.return_value = True
        mock_get_ev.return_value = [mock_event]
        mock_events_exp.return_value = []
        mock_rsvps_exp.return_value = []

        # 1. /event list
        await cog.list_events.callback(cog, mock_interaction)
        mock_interaction.response.send_message.assert_called()

        # 2. /event sheets
        await cog.sheets_export.callback(cog, mock_interaction)
        mock_interaction.followup.send.assert_called()

@pytest.mark.asyncio
async def test_event_commands_views_and_create(mock_bot, mock_interaction):
    cog = EventCommands(mock_bot)
    with patch("utils.auth.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("cogs.event_commands.cogs.event_cog.load_guild_translations", new_callable=AsyncMock), \
         patch("cogs.event_wizard.views.start_view.WizardStartView.refresh_message", new_callable=AsyncMock):

        mock_admin.return_value = True

        # 1. /event create
        await cog.create_event.callback(cog, mock_interaction)

        # 2. MyEventsView build
        my_ev = MyEventsView(mock_bot, guild_id=12345, user_id=999, events=[{
            "event_id": "EVT-1",
            "title": "My Raid",
            "start_time": time.time() + 3600,
            "channel_id": 67890,
            "message_id": 11111,
            "creator_id": "999",
            "user_status": "accepted"
        }])
        await my_ev.build()
        assert len(my_ev.children) > 0

        # 3. EventHistoryView build
        hist_ev = EventHistoryView(mock_bot, guild_id=12345, user_id=999, events=[{
            "event_id": "EVT-OLD",
            "title": "Old Raid",
            "start_time": time.time() - 7200,
            "channel_id": 67890,
            "message_id": 22222,
            "creator_id": "999",
            "user_status": "accepted",
            "attendance": "present"
        }])
        await hist_ev.build()
        assert len(hist_ev.children) > 0

@pytest.mark.asyncio
async def test_admin_commands_and_draft_commands(mock_bot, mock_interaction):
    draft_cog = DraftCommands(mock_bot)

    with patch("database.get_draft", new_callable=AsyncMock) as mock_get_draft, \
         patch("database.delete_draft", new_callable=AsyncMock) as mock_del_draft, \
         patch("cogs.event_wizard.EventWizardView.refresh_message", new_callable=AsyncMock):

        mock_get_draft.return_value = {"draft_id": "D-1", "data": "{}"}

        # /draft continue
        await draft_cog.continue_draft.callback(draft_cog, mock_interaction, draft_id="D-1")

        # /draft delete
        await draft_cog.delete_draft_cmd.callback(draft_cog, mock_interaction, draft_id="D-1")
        mock_del_draft.assert_called_once_with("D-1", 12345)

@pytest.mark.asyncio
async def test_attendance_and_emoji_views(mock_bot, mock_interaction):
    # Attendance View
    participants = [{"user_id": 101, "status": "accepted", "attended": 0}]
    att_view = AttendanceView(mock_bot, guild_id=12345, event_id="EVT-100", participants=participants)
    assert att_view.event_id == "EVT-100"

    # Emoji Views
    with patch("database.get_emoji_sets", new_callable=AsyncMock) as mock_sets, \
         patch("database.get_all_global_emoji_sets", new_callable=AsyncMock) as mock_g_sets:
        mock_sets.return_value = []
        mock_g_sets.return_value = [{"set_id": "standard", "name": "Standard", "data": "{}"}]

        wiz_view = EmojiWizardView(mock_bot, guild_id=12345)
        await wiz_view.refresh_message(mock_interaction)

        tpl_view = TemplateChoiceView(wiz_view)
        assert tpl_view.wizard_view == wiz_view

        del_view = ConfirmDeleteView(wiz_view, "custom1", "Custom 1")
        assert del_view.set_id == "custom1"

@pytest.mark.asyncio
async def test_message_wizard_and_master_commands(mock_bot, mock_interaction):
    # Message Wizard View
    with patch("database.get_guild_translations", new_callable=AsyncMock) as mock_trans, \
         patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_settings:
        mock_trans.return_value = {"KEY_TITLE": "Cím"}
        mock_settings.return_value = {}
        msg_view = MessageWizardView(mock_bot, guild_id="12345")
        await msg_view.prepare(mock_interaction)
        assert len(msg_view.children) > 0

    # Master Commands
    master_cog = MasterCommands(mock_bot)
    with patch("utils.auth.is_master", new_callable=AsyncMock) as mock_master, \
         patch("database.get_global_stats", new_callable=AsyncMock) as mock_stats:

        mock_master.return_value = True
        mock_stats.return_value = {"guilds": 5, "events": 10, "rsvps": 50}

        await master_cog.stats.callback(master_cog, mock_interaction)
        mock_interaction.followup.send.assert_called()
