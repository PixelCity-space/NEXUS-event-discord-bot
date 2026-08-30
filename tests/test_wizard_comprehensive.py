import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from cogs.event_wizard.state import WizardState
from cogs.event_wizard.views.start_view import WizardStartView
from cogs.event_wizard.views.wizard_view import EventWizardView
from cogs.event_wizard.actions.publisher import process_publish
from cogs.event_wizard.actions.preview import process_save_preview
from cogs.event_wizard.sections import (
    build_header_section,
    build_steps_row,
    build_recurrence_section,
    build_settings_section,
    build_notifications_section,
    build_emoji_set_section,
    build_actions_section,
)

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    chan = MagicMock()
    msg = MagicMock()
    msg.id = 888888
    chan.send = AsyncMock(return_value=msg)
    bot.get_channel = MagicMock(return_value=chan)
    bot.fetch_channel = AsyncMock(return_value=chan)
    guild = MagicMock()
    mock_role = MagicMock()
    mock_role.id = 99999
    guild.create_role = AsyncMock(return_value=mock_role)
    bot.get_guild.return_value = guild
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
    inter.response.is_done.return_value = False
    inter.edit_original_response = AsyncMock()
    inter.delete_original_response = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_wizard_state_lifecycle_and_defaults(mock_bot):
    with patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting, \
         patch("database.get_emoji_sets", new_callable=AsyncMock) as mock_emojis, \
         patch("database.get_all_global_emoji_sets", new_callable=AsyncMock) as mock_global_emojis, \
         patch("database.save_draft", new_callable=AsyncMock) as mock_save_draft:

        mock_setting.return_value = "12h"
        mock_emojis.return_value = []
        mock_global_emojis.return_value = [{"set_id": "standard", "name": "Standard", "data": "{}"}]

        state = WizardState(mock_bot, creator_id=999, guild_id=12345, existing_data={"title": "Raid", "start_str": "2026-10-10 20:00"})
        assert state.wizard_type == "single"
        assert state.steps_completed["step1"] is True

        await state.load_defaults()
        assert "repost_offset" in state.data

        await state.save_to_draft()
        mock_save_draft.assert_called_once()

@pytest.mark.asyncio
async def test_wizard_state_lobby_and_series(mock_bot):
    state_lobby = WizardState(mock_bot, creator_id=999, guild_id=12345, existing_data={"title": "Lobby", "lobby_mode": True})
    assert state_lobby.wizard_type == "lobby"
    assert state_lobby.steps_completed["step1"] is True

    state_series = WizardState(mock_bot, creator_id=999, guild_id=12345, existing_data={"title": "Series", "start_str": "2026-10-10 20:00", "recurrence_type": "weekly"})
    assert state_series.wizard_type == "series"
    assert state_series.steps_completed["step2"] is True

def test_wizard_sections_builders(mock_bot):
    wiz_view = EventWizardView(
        bot=mock_bot,
        creator_id=999,
        guild_id=12345,
        wizard_type="series",
        existing_data={
            "title": "Raid Night",
            "start_str": "2026-10-10 20:00",
            "description": "Weekly guild raid",
            "icon_set": "standard",
            "recurrence_type": "weekly",
            "reminder_type": "ping",
            "reminder_offsets": ["1h"],
        },
    )
    wiz_view.can_publish = True
    wiz_view.current_step = 1
    wiz_view.show_recurrence = True
    wiz_view.show_advanced = True
    wiz_view.show_reminder = True
    wiz_view.recurrence_options = [discord.SelectOption(label="Weekly", value="weekly")]

    h_items = build_header_section(wiz_view)
    assert len(h_items) > 0

    s_row = build_steps_row(wiz_view)
    assert isinstance(s_row, discord.ui.ActionRow)

    e_items = build_emoji_set_section(wiz_view)
    assert len(e_items) > 0

    wiz_view.current_step = 2
    r_items = build_recurrence_section(wiz_view)
    assert len(r_items) > 0

    wiz_view.current_step = 3
    set_items = build_settings_section(wiz_view)
    assert len(set_items) > 0

    notif_items = build_notifications_section(wiz_view)
    assert len(notif_items) > 0

    act_items = build_actions_section(wiz_view)
    assert len(act_items) > 0

@pytest.mark.asyncio
async def test_start_view_and_wizard_view(mock_bot, mock_interaction):
    start_view = WizardStartView(mock_bot, creator_id=999, guild_id=12345)
    await start_view.refresh_message(mock_interaction)
    mock_interaction.response.send_message.assert_called_once()

    with patch("cogs.event_wizard.state.WizardState.load_defaults", new_callable=AsyncMock):
        wiz_view = EventWizardView(mock_bot, creator_id=999, guild_id=12345, existing_data={"title": "Raid", "start_str": "2026-10-10 20:00"})
        await wiz_view.refresh_message(mock_interaction)
        assert await wiz_view.interaction_check(mock_interaction) is True

@pytest.mark.asyncio
async def test_process_publish_single_event(mock_bot, mock_interaction):
    wiz_view = EventWizardView(
        bot=mock_bot,
        creator_id=999,
        guild_id=12345,
        existing_data={
            "event_id": "EVT-NEW-1",
            "title": "Published Raid",
            "channel_id": 67890,
            "start_time": time.time() + 3600,
            "use_temp_role": True,
            "draft_id": "DRAFT-123",
        },
    )

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.create_active_event", new_callable=AsyncMock) as mock_create_ev, \
         patch("database.set_event_message", new_callable=AsyncMock) as mock_set_msg, \
         patch("database.delete_draft", new_callable=AsyncMock) as mock_del_draft, \
         patch("cogs.event_ui.DynamicEventView.prepare", new_callable=AsyncMock) as mock_prep:

        mock_get_ev.return_value = None
        await process_publish(wiz_view, mock_interaction)
        mock_create_ev.assert_called_once()
        mock_set_msg.assert_called_once()
        mock_del_draft.assert_called_once_with("DRAFT-123", 12345)
        mock_interaction.followup.send.assert_called()

@pytest.mark.asyncio
async def test_process_preview(mock_bot, mock_interaction):
    wiz_view = EventWizardView(
        bot=mock_bot,
        creator_id=999,
        guild_id=12345,
        existing_data={
            "event_id": "EVT-PREV",
            "title": "Preview Raid",
            "start_str": "2026-10-10 20:00",
            "start_time": time.time() + 3600,
        },
    )
    wiz_view.steps_completed["step1"] = True

    with patch("cogs.event_ui.DynamicEventView.prepare", new_callable=AsyncMock) as mock_prep:
        await process_save_preview(wiz_view, mock_interaction)
        mock_interaction.followup.send.assert_called()
