from services.recurrence_service import is_lobby_expired
from utils.enums import EventStatus
from utils.lobby_utils import (
    count_positive_rsvps,
    effective_lobby_capacity,
    lobby_is_full,
    positive_status_ids,
    role_limits_from_extra,
)


def test_integration_lobby_initialization_to_full_capacity():
    """Integration: Lobby setup -> role limit aggregation -> RSVP registrations until filled."""
    active_set = {
        "positive": ["tank", "heal", "dps"],
        "options": [
            {"id": "tank", "max_slots": 1},
            {"id": "heal", "max_slots": 1},
            {"id": "dps", "max_slots": 2},
            {"id": "maybe", "max_slots": 0},
        ],
    }
    pos_ids = positive_status_ids(active_set)
    assert pos_ids == ["tank", "heal", "dps"]

    # 1. Capacity calculation from roles (1 + 1 + 2 = 4)
    capacity = effective_lobby_capacity(max_accepted=0, active_set=active_set)
    assert capacity == 4

    # 2. Simulated RSVP additions
    rsvps = []
    assert lobby_is_full(count_positive_rsvps(rsvps, pos_ids), capacity) is False

    # 1 Tank joins
    rsvps.append({"user_id": 101, "status": "tank"})
    assert count_positive_rsvps(rsvps, pos_ids) == 1

    # 1 Healer joins
    rsvps.append({"user_id": 102, "status": "heal"})
    assert count_positive_rsvps(rsvps, pos_ids) == 2

    # 2 DPS join
    rsvps.append({"user_id": 103, "status": "dps"})
    rsvps.append({"user_id": 104, "status": "dps"})
    assert count_positive_rsvps(rsvps, pos_ids) == 4

    # 3. Verify lobby is full
    assert lobby_is_full(count_positive_rsvps(rsvps, pos_ids), capacity) is True

def test_integration_lobby_expiration_and_timeout():
    """Integration: Incomplete lobby exceeds expiry timestamp -> marked as expired."""
    now = 1780000000.0
    lobby_event = {
        "event_id": "LOBBY-001",
        "lobby_mode": True,
        "status": EventStatus.ACTIVE,
        "start_time": None, # Unstarted
        "lobby_expires_at": now - 60.0, # Expired 1 minute ago
    }

    assert is_lobby_expired(lobby_event, now) is True

    # Transition to terminal status
    lobby_event["status"] = EventStatus.LOBBY_EXPIRED
    assert lobby_event["status"].is_terminal is True
    assert lobby_event["status"].is_interactive is False

def test_integration_lobby_reopening_on_participant_leave():
    """Integration: Full lobby triggers start time -> participant leaves -> resets start time and reopens."""
    active_set = {
        "positive": ["player"],
        "options": [{"id": "player", "max_slots": 2}],
    }
    cap = effective_lobby_capacity(0, active_set)
    assert cap == 2
    pos_ids = ["player"]

    # 2 players filled
    rsvps = [{"user_id": 1, "status": "player"}, {"user_id": 2, "status": "player"}]
    assert lobby_is_full(count_positive_rsvps(rsvps, pos_ids), cap) is True

    # Player 2 leaves / changes to not_coming
    rsvps[1]["status"] = "not_coming"
    active_count = count_positive_rsvps(rsvps, pos_ids)
    assert active_count == 1
    assert lobby_is_full(active_count, cap) is False

def test_integration_lobby_role_limit_override_from_extra_data():
    """Integration: Custom role limits from JSON extra_data overriding icon set defaults."""
    active_set = {
        "positive": ["tank", "dps"],
        "options": [
            {"id": "tank", "max_slots": 1},
            {"id": "dps", "max_slots": 1},
        ],
    }
    extra_json = '{"role_limits": {"tank": 2, "dps": 4}}'
    role_limits = role_limits_from_extra(extra_json)
    assert role_limits == {"tank": 2, "dps": 4}

    # Capacity should calculate 2 + 4 = 6
    cap = effective_lobby_capacity(0, active_set, role_limits)
    assert cap == 6

def test_integration_lobby_waitlist_exclusion_from_capacity():
    """Integration: Waitlisted users (wait_*) do not occupy positive capacity slots."""
    active_set = {
        "positive": ["tank"],
        "options": [{"id": "tank", "max_slots": 1}],
    }
    cap = effective_lobby_capacity(0, active_set)
    assert cap == 1

    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "wait_tank"}, # Waitlisted
        {"user_id": 103, "status": "wait_tank"}, # Waitlisted
    ]
    # Only 1 user should count as active positive RSVP
    assert count_positive_rsvps(rsvps, ["tank"]) == 1
    assert lobby_is_full(count_positive_rsvps(rsvps, ["tank"]), cap) is True
