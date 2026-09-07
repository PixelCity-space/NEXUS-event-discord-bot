import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.event_ui.card_builder import (
    build_card_buttons,
    build_card_container,
    update_button_states,
)
from cogs.event_ui.participant_formatter import (
    ParticipantFormatter,
    ParticipantRosterData,
)
from utils.enums import EventStatus


@pytest.fixture
def base_active_set():
    return {
        "options": [
            {"id": "tank", "label": "Tank", "emoji": "🛡️", "button_color": "primary", "positive": True, "max_slots": 2},
            {"id": "healer", "label": "Healer", "emoji": "💚", "button_color": "success", "positive": True, "max_slots": 2},
            {"id": "dps", "label": "DPS", "emoji": "⚔️", "button_color": "danger", "positive": True, "max_slots": 5},
            {"id": "declined", "label_key": "BTN_DECLINED", "emoji": "❌", "button_color": "secondary", "positive": False},
        ],
        "buttons_per_row": 5,
        "show_mgmt": True,
    }

def test_participant_formatter_basic(base_active_set):
    event_conf = {
        "title": "Raid Night",
        "description": "Weekly guild raid",
        "max_accepted": 5,
        "guild_id": 12345,
    }
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "tank"},
        {"user_id": 103, "status": "wait_tank"},
        {"user_id": 104, "status": "dps"},
        {"user_id": 105, "status": "declined"},
    ]
    roster_data = ParticipantFormatter.format_roster(
        active_set=base_active_set,
        rsvps=rsvps,
        event_conf=event_conf,
    )
    assert isinstance(roster_data, ParticipantRosterData)
    assert roster_data.status_counts["tank"] == 2
    assert roster_data.total_positive_count == 3
    assert len(roster_data.waiting_list) == 1
    assert not roster_data.is_full

def test_participant_formatter_role_limits_and_full(base_active_set):
    event_conf = {
        "title": "Dungeon",
        "max_accepted": 2,
        "extra_data": '{"role_limits": {"tank": 1, "dps": 1}}',
    }
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 104, "status": "dps"},
    ]
    roster_data = ParticipantFormatter.format_roster(
        active_set=base_active_set,
        rsvps=rsvps,
        event_conf=event_conf,
    )
    assert roster_data.is_full
    assert roster_data.role_limits.get("tank") == 1
    assert roster_data.role_limits.get("dps") == 1

def test_build_card_container_regular_event(base_active_set):
    mock_bot = MagicMock()
    mock_user = MagicMock()
    mock_user.display_name = "GuildMaster"
    mock_bot.get_user.return_value = mock_user

    event_conf = {
        "title": "Dragon Slayer",
        "description": "Epic battle awaits",
        "start_time": time.time() + 3600,
        "end_time": time.time() + 7200,
        "creator_id": "999999",
        "color": "0x1FAD5E",
        "recurrence_type": "weekly",
        "image_urls": "https://example.com/banner1.png, https://example.com/banner2.png",
        "max_accepted": 1,
    }
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "wait_tank"},
    ]

    container = build_card_container(
        bot=mock_bot,
        event_id="EVT-TEST-1",
        event_conf=event_conf,
        db_event=None,
        active_set=base_active_set,
        rsvps=rsvps,
    )
    assert isinstance(container, discord.ui.Container)
    assert container.accent_color is not None

def test_build_card_container_lobby_modes(base_active_set):
    mock_bot = MagicMock()
    # 1. Unstarted lobby
    event_conf_lobby_unstarted = {
        "title": "Quick Match",
        "lobby_mode": True,
        "status": "active",
        "lobby_expires_at": time.time() + 1800,
    }
    c1 = build_card_container(mock_bot, "EVT-LOBBY-1", event_conf_lobby_unstarted, None, base_active_set, [])
    assert isinstance(c1, discord.ui.Container)

    # 2. Started lobby with different start and end dates
    now = time.time()
    event_conf_lobby_started = {
        "title": "Quick Match Started",
        "lobby_mode": True,
        "start_time": now + 600,
        "end_time": now + 86400 * 2,
        "status": "active",
    }
    c2 = build_card_container(mock_bot, "EVT-LOBBY-2", event_conf_lobby_started, None, base_active_set, [])
    assert isinstance(c2, discord.ui.Container)

    # 3. Expired lobby
    event_conf_lobby_expired = {
        "title": "Quick Match Expired",
        "lobby_mode": True,
        "status": EventStatus.LOBBY_EXPIRED,
    }
    c3 = build_card_container(mock_bot, "EVT-LOBBY-3", event_conf_lobby_expired, None, base_active_set, [])
    assert isinstance(c3, discord.ui.Container)

def test_build_card_container_statuses_and_images(base_active_set):
    mock_bot = MagicMock()
    mock_bot.get_user.return_value = None

    statuses = [
        EventStatus.CANCELLED,
        EventStatus.POSTPONED,
        EventStatus.DELETED,
        EventStatus.RESCHEDULED,
        EventStatus.CLOSED,
    ]
    for st in statuses:
        conf = {
            "title": f"Event {st}",
            "status": st,
            "image_urls": ["https://example.com/img1.png", "https://example.com/img2.png"],
            "creator_id": "System",
            "end_time": time.time() + 86400 * 2,
            "start_time": time.time(),
        }
        c = build_card_container(mock_bot, f"EVT-{st}", conf, None, base_active_set, [])
        assert isinstance(c, discord.ui.Container)

@pytest.mark.asyncio
async def test_build_card_buttons_action_rows_and_callbacks(base_active_set):
    mock_view = MagicMock()
    mock_view.handle_rsvp = AsyncMock()
    event_conf = {"status": "active", "guild_id": 123}
    rows = build_card_buttons(mock_view, "EVT-01", event_conf, None, base_active_set, [])
    assert len(rows) > 0
    assert any(isinstance(r, discord.ui.ActionRow) for r in rows)

    # Trigger button callback
    btn = rows[0].children[0]
    mock_interaction = MagicMock()
    await btn.callback(mock_interaction)
    mock_view.handle_rsvp.assert_called_once()

def test_build_card_buttons_many_options(base_active_set):
    mock_view = MagicMock()
    large_set = {
        "options": [{"id": f"opt_{i}", "label": f"Opt {i}", "button_color": "secondary"} for i in range(12)],
        "buttons_per_row": 3,
        "show_mgmt": True,
    }
    event_conf = {"status": "active", "guild_id": 123}
    rows = build_card_buttons(mock_view, "EVT-MANY", event_conf, None, large_set, [])
    assert len(rows) >= 4

def test_build_card_buttons_postponed_and_mgmt(base_active_set):
    mock_view = MagicMock()
    mock_view.reschedule_callback = MagicMock()
    mock_view.cancel_callback = MagicMock()
    event_conf = {"status": "postponed", "guild_id": 123}
    rows = build_card_buttons(mock_view, "EVT-02", event_conf, None, base_active_set, [])
    assert len(rows) > 0

def test_update_button_states_disabled_statuses(base_active_set):
    mock_view = MagicMock()
    btn1 = discord.ui.Button(label="Tank", custom_id="tank_EVT-01")
    btn2 = discord.ui.Button(label="Cancel", custom_id="cancel_EVT-01")
    row = discord.ui.ActionRow(btn1, btn2)
    mock_view.children = [row]

    # Inactive status disables RSVP button
    event_conf = {"status": EventStatus.CANCELLED, "use_waiting_list": False}
    update_button_states(mock_view, [], event_conf, base_active_set)
    assert btn1.disabled is True

def test_update_button_states_waiting_list_enabled(base_active_set):
    mock_view = MagicMock()
    btn1 = discord.ui.Button(label="Tank", custom_id="tank_EVT-01")
    btn_edit = discord.ui.Button(label="Edit", custom_id="edit_EVT-01")
    row = discord.ui.ActionRow(btn1, btn_edit)
    mock_view.children = [row]

    # With waiting list enabled, buttons remain clickable
    event_conf = {"status": "active", "use_waiting_list": True}
    update_button_states(mock_view, [], event_conf, base_active_set)
    assert btn1.disabled is False

def test_update_button_states_capacity_reached(base_active_set):
    mock_view = MagicMock()
    btn_tank = discord.ui.Button(label="Tank", custom_id="tank_EVT-01")
    btn_dps = discord.ui.Button(label="DPS", custom_id="dps_EVT-01")
    row = discord.ui.ActionRow(btn_tank, btn_dps)
    mock_view.children = [row]

    # Role limit saturated
    event_conf = {"status": "active", "use_waiting_list": False, "max_accepted": 10}
    rsvps = [
        {"user_id": 1, "status": "tank"},
        {"user_id": 2, "status": "tank"},  # max_slots in base_active_set is 2
    ]
    update_button_states(mock_view, rsvps, event_conf, base_active_set)
    assert btn_tank.disabled is True
    assert btn_dps.disabled is False

def test_update_button_states_max_accepted_reached(base_active_set):
    mock_view = MagicMock()
    btn_tank = discord.ui.Button(label="Tank", custom_id="tank_EVT-01")
    btn_dps = discord.ui.Button(label="DPS", custom_id="dps_EVT-01")
    row = discord.ui.ActionRow(btn_tank, btn_dps)
    mock_view.children = [row]

    # Total positive event capacity saturated
    event_conf = {"status": "active", "use_waiting_list": False, "max_accepted": 2}
    rsvps = [
        {"user_id": 1, "status": "tank"},
        {"user_id": 2, "status": "dps"},
    ]
    update_button_states(mock_view, rsvps, event_conf, base_active_set)
    assert btn_tank.disabled is True
    assert btn_dps.disabled is True
