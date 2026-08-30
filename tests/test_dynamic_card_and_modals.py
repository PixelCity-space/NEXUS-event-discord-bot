import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from utils.enums import EventStatus
from cogs.event_ui.views.dynamic_card import DynamicEventView
from cogs.event_ui.modals.postpone import PostponeModal

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.is_owner = AsyncMock(return_value=False)
    bot.get_user = MagicMock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    mock_chan = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = 888888
    mock_chan.send = AsyncMock(return_value=mock_msg)
    bot.fetch_channel = AsyncMock(return_value=mock_chan)
    bot.get_channel = MagicMock(return_value=mock_chan)
    return bot

@pytest.fixture
def mock_interaction(mock_bot):
    inter = MagicMock(spec=discord.Interaction)
    inter.client = mock_bot
    inter.guild_id = 12345
    inter.channel_id = 67890
    inter.user = MagicMock(spec=discord.Member)
    inter.user.id = 999
    inter.guild = MagicMock()
    inter.guild.me.guild_permissions.manage_roles = True
    inter.message = MagicMock()
    inter.message.edit = AsyncMock()
    inter.response = MagicMock()
    inter.response.send_message = AsyncMock()
    inter.response.send_modal = AsyncMock()
    inter.response.defer = AsyncMock()
    inter.response.is_done = MagicMock(return_value=False)
    inter.response.edit_message = AsyncMock()
    inter.edit_original_response = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_dynamic_event_view_preview_mode(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-PREV", is_preview=True)
    check_result = await view.interaction_check(mock_interaction)
    assert check_result is False
    mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_dynamic_event_view_prepare(mock_bot):
    db_event = {
        "event_id": "EVT-100",
        "title": "Guild Raid",
        "config_name": "raid",
        "guild_id": "12345",
        "status": "active",
        "start_time": time.time() + 3600,
        "extra_data": '{"lobby_mode": false}',
    }
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps", new_callable=AsyncMock) as mock_get_rsvps:
        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = []

        view = DynamicEventView(mock_bot, "EVT-100")
        await view.prepare()
        assert len(view.children) > 0

@pytest.mark.asyncio
async def test_dynamic_event_view_cancel_callback(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-100", {"title": "Raid", "status": "active"})
    view.prepare = AsyncMock()

    with patch("cogs.event_ui.views.dynamic_card.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("database.update_event_status", new_callable=AsyncMock) as mock_up_st, \
         patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("cogs.event_ui.views.dynamic_card.send_status_notification", new_callable=AsyncMock) as mock_send_notif:

        mock_admin.return_value = True
        mock_get_ev.return_value = {"event_id": "EVT-100", "title": "Raid", "status": "cancelled"}

        await view.cancel_callback(mock_interaction)
        mock_up_st.assert_called_once_with("EVT-100", "cancelled")
        mock_interaction.message.edit.assert_called_once()
        mock_send_notif.assert_called_once()

@pytest.mark.asyncio
async def test_dynamic_event_view_delete_callback(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-100", {"title": "Raid", "status": "active"})
    mock_role = MagicMock()
    mock_role.delete = AsyncMock()
    mock_interaction.guild.get_role.return_value = mock_role

    with patch("cogs.event_ui.views.dynamic_card.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.delete_active_event", new_callable=AsyncMock) as mock_del_ev, \
         patch("database.get_rsvps", new_callable=AsyncMock) as mock_get_rsvps:

        mock_admin.return_value = True
        mock_get_ev.return_value = {"event_id": "EVT-100", "temp_role_id": 999}
        mock_get_rsvps.return_value = []

        await view.delete_callback(mock_interaction)
        mock_del_ev.assert_called_once_with("EVT-100")
        mock_role.delete.assert_called_once()

@pytest.mark.asyncio
async def test_dynamic_event_view_modals(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-100")
    with patch("cogs.event_ui.views.dynamic_card.is_admin", new_callable=AsyncMock) as mock_admin:
        mock_admin.return_value = True
        await view.postpone_callback(mock_interaction)
        assert mock_interaction.response.send_modal.call_count == 1
        await view.reschedule_callback(mock_interaction)
        assert mock_interaction.response.send_modal.call_count == 2

@pytest.mark.asyncio
async def test_dynamic_event_view_delegates(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-100", {"title": "Raid", "status": "active"})
    with patch("cogs.event_ui.views.dynamic_card.rsvp_handler", new_callable=AsyncMock) as mock_rsvp, \
         patch("cogs.event_ui.views.dynamic_card.notify_promotion_fn", new_callable=AsyncMock) as mock_notif, \
         patch("cogs.event_ui.views.dynamic_card.promote_handler", new_callable=AsyncMock) as mock_prom:

        await view.handle_rsvp(mock_interaction, "accepted")
        mock_rsvp.assert_called_once()

        await view.notify_promotion(mock_interaction, 999, {"id": "accepted"})
        mock_notif.assert_called_once()

        await view.try_promote_waiting(mock_interaction, {}, {})
        mock_prom.assert_called_once()

@pytest.mark.asyncio
async def test_dynamic_event_view_edit_callback_admin_and_wizard(mock_bot, mock_interaction):
    view = DynamicEventView(mock_bot, "EVT-100", {"title": "Raid", "status": "active"})
    db_event = {
        "event_id": "EVT-100",
        "config_name": "manual",
        "timezone": "UTC",
        "start_time": time.time() + 3600,
        "end_time": time.time() + 7200,
    }

    with patch("cogs.event_ui.views.dynamic_card.is_admin", new_callable=AsyncMock) as mock_admin, \
         patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("cogs.event_wizard.EventWizardView.refresh_message", new_callable=AsyncMock) as mock_refresh:

        mock_admin.return_value = True
        mock_get_ev.return_value = db_event

        await view.edit_callback(mock_interaction)
        mock_refresh.assert_called_once()

@pytest.mark.asyncio
async def test_postpone_modal_empty_start_postpones(mock_bot, mock_interaction):
    parent_view = MagicMock()
    parent_view.prepare = AsyncMock()
    parent_view.children = []
    parent_view.event_conf = {}

    modal = PostponeModal(mock_bot, "EVT-100", parent_view, 12345)
    modal.start_input._value = ""

    db_event = {"event_id": "EVT-100", "title": "Raid", "status": "active"}

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.update_active_event", new_callable=AsyncMock) as mock_up_ev, \
         patch("cogs.event_ui.modals.postpone.send_status_notification", new_callable=AsyncMock) as mock_notif:

        mock_get_ev.return_value = db_event

        await modal.on_submit(mock_interaction)
        mock_up_ev.assert_called_once()
        mock_notif.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_postpone_modal_invalid_date(mock_bot, mock_interaction):
    parent_view = MagicMock()
    modal = PostponeModal(mock_bot, "EVT-100", parent_view, 12345)
    modal.start_input._value = "not a valid date string 99999"

    db_event = {"event_id": "EVT-100", "title": "Raid", "status": "active"}

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev:
        mock_get_ev.return_value = db_event

        await modal.on_submit(mock_interaction)
        mock_interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_postpone_modal_reschedule_success(mock_bot, mock_interaction):
    parent_view = MagicMock()
    parent_view.prepare = AsyncMock()
    parent_view.children = []
    parent_view.event_conf = {}

    modal = PostponeModal(mock_bot, "EVT-100", parent_view, 12345)
    modal.start_input._value = "2026-12-01 18:00"
    modal.end_input._value = "2026-12-01 21:00"

    db_event = {
        "event_id": "EVT-100",
        "title": "Raid",
        "status": "active",
        "channel_id": "67890",
        "ping_role": 555,
    }

    mock_user = MagicMock()
    mock_user.send = AsyncMock()
    mock_bot.get_user.return_value = mock_user

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.update_active_event", new_callable=AsyncMock) as mock_up_ev, \
         patch("database.set_event_message", new_callable=AsyncMock) as mock_set_msg, \
         patch("database.get_rsvps", new_callable=AsyncMock) as mock_rsvps, \
         patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting:

        mock_get_ev.return_value = db_event
        mock_rsvps.return_value = [(101, "accepted")]
        mock_setting.return_value = "dm"

        await modal.on_submit(mock_interaction)
        mock_up_ev.assert_called_once()
        mock_set_msg.assert_called_once_with("EVT-100", 888888)
        mock_user.send.assert_called_once()
