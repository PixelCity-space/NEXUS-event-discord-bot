from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.attendance.cogs.attendance_cog import AttendanceCog
from cogs.attendance.views.attendance_view import AttendanceView
from cogs.emoji_wizard.modals.edit_set import EditEmojiSetModal
from cogs.event_commands.helpers import handle_status_change
from utils.enums import EventStatus


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 12345678
    bot.is_owner = AsyncMock(return_value=True)
    bot.get_guild = MagicMock()
    bot.get_channel = MagicMock()
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
async def test_attendance_cog_manage(mock_bot, mock_interaction):
    cog = AttendanceCog(mock_bot)
    mock_event = {
        "event_id": "EVT-100",
        "guild_id": "12345",
        "title": "Raid",
        "icon_set": "standard",
    }
    participants = [{"user_id": 101, "status": "accepted", "attendance": "unmarked"}]

    with patch("cogs.attendance.cogs.attendance_cog.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("services.attendance_service.get_eligible_attendance_participants", new_callable=AsyncMock) as mock_elig, \
         patch("services.attendance_service.resolve_member_names_batch", new_callable=AsyncMock) as mock_names:

        mock_admin.return_value = True
        mock_get_ev.return_value = mock_event
        mock_elig.return_value = participants
        mock_names.return_value = {"101": "PlayerOne"}

        await cog.manage_attendance.callback(cog, mock_interaction, event_id="EVT-100")
        mock_interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_attendance_view_build_and_toggle(mock_bot, mock_interaction):
    participants = [
        {"user_id": 101, "status": "accepted", "attendance": "unmarked"},
        {"user_id": 102, "status": "accepted", "attendance": "present"},
    ]
    with patch("services.attendance_service.resolve_member_names_batch", new_callable=AsyncMock) as mock_names, \
         patch("services.attendance_service.toggle_user_attendance", new_callable=AsyncMock):

        mock_names.return_value = {"101": "PlayerOne", "102": "PlayerTwo"}
        view = AttendanceView(mock_bot, event_id="EVT-100", participants=participants, guild_id="12345", title="Test Raid")
        await view.build()
        assert len(view.children) > 0

@pytest.mark.asyncio
async def test_edit_emoji_set_modal(mock_interaction):
    mock_wizard = MagicMock()
    mock_wizard.guild_id = 12345
    mock_wizard.is_global = False
    mock_wizard.refresh_message = AsyncMock()

    set_record = {
        "set_id": "custom1",
        "name": "Custom 1",
        "data": {
            "options": [
                {"emoji": "🛡️", "label": "Tank", "list_label": "Tanks", "max_slots": 2, "button_style": "both", "button_color": "primary"}
            ],
            "buttons_per_row": 5,
            "show_mgmt": True
        }
    }

    modal = EditEmojiSetModal(mock_wizard, set_record)
    modal.name_input._value = "Updated Custom 1"
    modal.opts_input._value = "🛡️ | Tank | Tanks | 2 | BP"

    with patch("database.save_emoji_set", new_callable=AsyncMock) as mock_save:
        await modal.on_submit(mock_interaction)
        mock_save.assert_called_once()
        mock_wizard.refresh_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_status_change_single_and_series(mock_bot, mock_interaction):
    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("cogs.event_commands.helpers.resolve_target_events", new_callable=AsyncMock) as mock_resolve, \
         patch("database.update_event_status", new_callable=AsyncMock) as mock_upd_status, \
         patch("database.get_active_events_by_config", new_callable=AsyncMock) as mock_series_events:

        mock_admin.return_value = True
        mock_event = {"event_id": "EVT-1", "config_name": "manual"}
        mock_resolve.return_value = (mock_event, [mock_event], None)
        mock_series_events.return_value = [mock_event]

        # 1. Single Event Cancel
        await handle_status_change(mock_bot, mock_interaction, "EVT-1", EventStatus.CANCELLED, notify_type="none")
        mock_upd_status.assert_called_once_with("EVT-1", EventStatus.CANCELLED)
        mock_interaction.followup.send.assert_called()

        # 2. Series Event with choice
        mock_series_event = {"event_id": "EVT-S1", "config_name": "weekly_raid"}
        mock_resolve.return_value = (mock_series_event, [mock_series_event, {"event_id": "EVT-S2"}], None)
        mock_series_events.return_value = [{"event_id": "EVT-S1"}, {"event_id": "EVT-S2"}]

        mock_interaction.followup.send.reset_mock()
        await handle_status_change(mock_bot, mock_interaction, "EVT-S1", EventStatus.POSTPONED, notify_type="none")
        mock_interaction.followup.send.assert_called()
