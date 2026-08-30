import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from utils.enums import EventStatus
from cogs.event_ui.rsvp_manager import handle_rsvp, try_promote_waiting, _rsvp_cooldowns
from cogs.event_ui.notifications import send_status_notification, notify_promotion, send_lobby_fill_notifications
from cogs.event_ui.lobby import process_lobby_transition

@pytest.fixture(autouse=True)
def clear_cooldowns():
    _rsvp_cooldowns.clear()
    yield
    _rsvp_cooldowns.clear()

@pytest.fixture
def mock_view():
    view = MagicMock()
    view.event_id = "EVT-100"
    view.bot = MagicMock()
    view.event_conf = {"title": "Raid", "status": "active", "max_accepted": 5, "use_waiting_list": True}
    view.active_set = {
        "options": [
            {"id": "accepted", "label": "Going", "positive": True, "max_slots": 2},
            {"id": "tentative", "label": "Maybe", "positive": False},
            {"id": "declined", "label": "Decline", "positive": False},
        ],
        "positive": ["accepted"],
    }
    view.prepare = AsyncMock()
    return view

@pytest.fixture
def mock_interaction():
    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 123456
    inter.channel_id = 789012
    inter.user = MagicMock(spec=discord.Member)
    inter.user.id = 999
    inter.user.roles = []
    inter.user.send = AsyncMock()
    inter.guild = MagicMock()
    inter.guild.me.guild_permissions.manage_roles = True
    inter.response = MagicMock()
    inter.response.send_message = AsyncMock()
    inter.response.defer = AsyncMock()
    inter.response.is_done = MagicMock(return_value=False)
    inter.response.edit_message = AsyncMock()
    inter.edit_original_response = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.edit_message = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_handle_rsvp_event_not_found(mock_view, mock_interaction):
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_cooldown_enforced(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "use_waiting_list": True,
        "config_name": "raid",
    }
    _rsvp_cooldowns[("EVT-100", mock_interaction.user.id)] = time.time()
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = db_event
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_lobby_expired_and_inactive(mock_view, mock_interaction):
    # Inactive event
    db_event = {"event_id": "EVT-100", "status": EventStatus.CANCELLED, "use_waiting_list": False}
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = db_event
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

    # Expired lobby
    mock_interaction.response.send_message.reset_mock()
    db_lobby = {
        "event_id": "EVT-100",
        "status": "active",
        "lobby_mode": True,
        "start_time": None,
        "lobby_expires_at": time.time() - 100,
    }
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = db_lobby
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_role_permission_check(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "rsvp_allowed_role_ids": "777,888",
    }
    r1 = MagicMock()
    r1.id = 111
    mock_interaction.user.roles = [r1]

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = db_event
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_role_permission_not_member(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "rsvp_allowed_role_ids": "777",
    }
    mock_interaction.user = MagicMock(spec=discord.User)  # User, not Member
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = db_event
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_success_and_temp_role(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "config_name": "raid",
        "temp_role_id": 55555,
        "guild_id": "123456",
    }
    mock_role = MagicMock()
    mock_role.id = 55555
    mock_interaction.guild.get_role.return_value = mock_role
    mock_interaction.user.roles = []
    mock_interaction.user.add_roles = AsyncMock()
    mock_interaction.user.remove_roles = AsyncMock()

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_get_rsvps, \
         patch("database.update_rsvp", new_callable=AsyncMock) as mock_update_rsvp:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = []

        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_update_rsvp.assert_called_once_with("EVT-100", mock_interaction.user.id, "accepted")
        mock_interaction.user.add_roles.assert_called_once_with(mock_role, reason="RSVP positive: EVT-100")

@pytest.mark.asyncio
async def test_handle_rsvp_role_limit_and_waitlist_full(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "config_name": "raid",
        "use_waiting_list": True,
        "extra_data": '{"role_limits": {"accepted": 1, "waiting_list_limit": 1}}',
    }
    mock_view.event_conf = dict(db_event)
    existing_rsvps = [
        {"user_id": 111, "status": "accepted", "joined_at": time.time()},
        {"user_id": 222, "status": "wait_accepted", "joined_at": time.time()},
    ]

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_get_rsvps:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = existing_rsvps

        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_overflow_to_waitlist(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "config_name": "raid",
        "max_accepted": 1,
        "use_waiting_list": True,
    }
    mock_view.event_conf = dict(db_event)
    existing_rsvps = [{"user_id": 111, "status": "accepted", "joined_at": time.time()}]

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_get_rsvps, \
         patch("database.update_rsvp", new_callable=AsyncMock) as mock_update_rsvp:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = existing_rsvps

        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_update_rsvp.assert_called_once_with("EVT-100", mock_interaction.user.id, "wait_accepted")
        mock_interaction.user.send.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_leaving_removes_temp_role(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "config_name": "raid",
        "temp_role_id": 55555,
        "guild_id": "123456",
    }
    mock_role = MagicMock()
    mock_role.id = 55555
    mock_interaction.guild.get_role.return_value = mock_role
    mock_interaction.user.roles = [mock_role]
    mock_interaction.user.remove_roles = AsyncMock()

    existing_rsvps = [{"user_id": mock_interaction.user.id, "status": "accepted", "joined_at": time.time()}]

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_get_rsvps, \
         patch("database.update_rsvp", new_callable=AsyncMock) as mock_update_rsvp, \
         patch("cogs.event_ui.rsvp_manager.try_promote_waiting", new_callable=AsyncMock) as mock_promote:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = existing_rsvps

        await handle_rsvp(mock_view, mock_interaction, "declined")
        mock_update_rsvp.assert_called_once_with("EVT-100", mock_interaction.user.id, "declined")
        mock_interaction.user.remove_roles.assert_called_once_with(mock_role, reason="RSVP negative/left: EVT-100")
        mock_promote.assert_called_once()

@pytest.mark.asyncio
async def test_try_promote_waiting(mock_view, mock_interaction):
    mock_bot = MagicMock()
    mock_bot.get_channel = MagicMock(return_value=None)
    mock_bot.fetch_channel = AsyncMock(return_value=None)

    with patch("database.promote_waiting_users_atomic", new_callable=AsyncMock) as mock_promote, \
         patch("cogs.event_ui.rsvp_manager.notify_promotion", new_callable=AsyncMock) as mock_notify:

        mock_promote.return_value = [(222, "accepted")]
        rsvps = [{"user_id": 222, "status": "wait_accepted"}]

        await try_promote_waiting(
            bot=mock_bot,
            event_id="EVT-100",
            event_conf=mock_view.event_conf,
            active_set=mock_view.active_set,
            interaction=mock_interaction,
            db_event={"event_id": "EVT-100"},
            role_limits={},
            rsvps=rsvps,
        )
        assert rsvps[0]["status"] == "accepted"
        mock_notify.assert_called_once()

@pytest.mark.asyncio
async def test_process_lobby_transition():
    mock_bot = MagicMock()
    mock_chan = MagicMock()
    mock_chan.send = AsyncMock()
    mock_bot.get_channel.return_value = mock_chan

    db_event = {
        "event_id": "EVT-LOBBY",
        "channel_id": "12345",
        "guild_id": "999",
        "lobby_mode": True,
        "start_time": None,
        "extra_data": '{"lobby_auto_start_offset": "1h"}',
        "lobby_remind_on_fill": True,
    }
    rsvps = [
        {"user_id": 1, "status": "accepted"},
        {"user_id": 2, "status": "accepted"},
    ]
    active_set = {
        "options": [{"id": "accepted", "positive": True, "max_slots": 2}],
        "positive": ["accepted"],
    }

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps", new_callable=AsyncMock) as mock_get_rsvps, \
         patch("database.set_lobby_start_time", new_callable=AsyncMock) as mock_set_lobby, \
         patch("database.update_event_time", new_callable=AsyncMock) as mock_up_time, \
         patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = rsvps
        mock_setting.return_value = "none"

        await process_lobby_transition(mock_bot, "EVT-LOBBY", active_set, 999)
        mock_set_lobby.assert_called_once()

@pytest.mark.asyncio
async def test_send_status_notification():
    mock_bot = MagicMock()
    db_event = {
        "channel_id": "12345",
        "title": "Big Raid",
        "ping_role": 999,
        "guild_id": "123",
    }

    with patch("database.get_rsvps", new_callable=AsyncMock) as mock_rsvps, \
         patch("database.get_guild_setting", new_callable=AsyncMock) as mock_setting, \
         patch("cogs.event_ui.notifications.send_event_alert", new_callable=AsyncMock) as mock_alert:

        mock_rsvps.return_value = [{"user_id": 100, "status": "accepted"}]
        mock_setting.return_value = "dm"

        await send_status_notification(
            bot=mock_bot,
            event_id="EVT-100",
            db_event=db_event,
            status_name="cancelled",
            guild_id=123,
        )
        mock_alert.assert_called_once()

@pytest.mark.asyncio
async def test_send_lobby_fill_notifications():
    mock_bot = MagicMock()
    db_event = {
        "event_id": "EVT-LOBBY",
        "channel_id": "12345",
        "title": "Quick Match",
        "reminder_type": "channel",
        "start_time": time.time(),
    }
    active_set = {
        "options": [{"id": "accepted", "positive": True}],
        "positive": ["accepted"],
    }
    with patch("database.get_rsvps", new_callable=AsyncMock) as mock_rsvps, \
         patch("cogs.event_ui.notifications.send_event_alert", new_callable=AsyncMock) as mock_alert:
        mock_rsvps.return_value = [{"user_id": 100, "status": "accepted"}]
        await send_lobby_fill_notifications(mock_bot, db_event, active_set, 123)
        mock_alert.assert_called_once()

@pytest.mark.asyncio
async def test_notify_promotion():
    mock_bot = MagicMock()
    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 123
    inter.channel_id = 456
    inter.guild = MagicMock()
    mock_member = MagicMock()
    mock_member.roles = []
    mock_member.add_roles = AsyncMock()
    inter.guild.get_member.return_value = mock_member
    mock_role = MagicMock()
    inter.guild.get_role.return_value = mock_role

    event_conf = {"notify_promotion": "dm", "title": "Raid", "extra_data": '{"custom_promo_msg": "Congrats {user_id} as {role}!"}'}
    db_event = {
        "event_id": "EVT-1",
        "channel_id": "456",
        "message_id": "789",
        "temp_role_id": 111,
    }
    opt = {"id": "accepted", "label": "Going"}

    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("cogs.event_ui.notifications.send_event_alert", new_callable=AsyncMock) as mock_alert:
        mock_get_ev.return_value = db_event
        await notify_promotion(mock_bot, inter, "EVT-1", event_conf, 100, opt)
        mock_alert.assert_called_once()
        mock_member.add_roles.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_waitlist_limit_reached(mock_view, mock_interaction):
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "use_waiting_list": True,
        "extra_data": '{"role_limits": {"accepted": 1, "waiting_list_limit": 1}}'
    }
    rsvps = [
        {"user_id": 101, "status": "accepted", "rsvp_time": time.time() - 100},
        {"user_id": 102, "status": "wait_accepted", "rsvp_time": time.time() - 50},
    ]
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_rsvps:
        mock_get.return_value = db_event
        mock_rsvps.return_value = rsvps
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_position_full_no_waitlist(mock_view, mock_interaction):
    mock_view.event_conf["use_waiting_list"] = False
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "use_waiting_list": False,
        "extra_data": '{"role_limits": {"accepted": 1}}'
    }
    rsvps = [
        {"user_id": 101, "status": "accepted", "rsvp_time": time.time() - 100}
    ]
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_rsvps:
        mock_get.return_value = db_event
        mock_rsvps.return_value = rsvps
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_handle_rsvp_max_accepted_capacity_overflow(mock_view, mock_interaction):
    mock_view.event_conf["max_accepted"] = 1
    mock_view.event_conf["use_waiting_list"] = True
    db_event = {
        "event_id": "EVT-100",
        "status": "active",
        "use_waiting_list": True,
        "max_accepted": 1,
    }
    rsvps = [
        {"user_id": 101, "status": "accepted", "rsvp_time": time.time() - 100}
    ]
    with patch("database.get_active_event", new_callable=AsyncMock) as mock_get, \
         patch("database.get_rsvps_with_time", new_callable=AsyncMock) as mock_rsvps, \
         patch("database.update_rsvp", new_callable=AsyncMock) as mock_upd, \
         patch("cogs.event_ui.rsvp_manager.try_promote_waiting", new_callable=AsyncMock):
        mock_get.return_value = db_event
        mock_rsvps.return_value = rsvps
        await handle_rsvp(mock_view, mock_interaction, "accepted")
        mock_upd.assert_called_once_with("EVT-100", mock_interaction.user.id, "wait_accepted")


