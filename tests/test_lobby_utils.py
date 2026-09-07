from utils.lobby_utils import (
    count_positive_rsvps,
    effective_lobby_capacity,
    lobby_is_full,
    positive_status_ids,
    role_limits_from_extra,
)


def test_positive_status_ids_from_list():
    """Test extracting positive status IDs when explicitly given in active_set."""
    active_set = {
        "positive": ["coming", "spectate"],
        "options": [{"id": "coming"}, {"id": "spectate"}, {"id": "declined"}]
    }
    assert positive_status_ids(active_set) == ["coming", "spectate"]

def test_positive_status_ids_from_count():
    """Test extracting positive status IDs derived from positive_count slice."""
    active_set = {
        "positive_count": 2,
        "options": [{"id": "tank"}, {"id": "heal"}, {"id": "maybe"}, {"id": "no"}]
    }
    assert positive_status_ids(active_set) == ["tank", "heal"]

def test_effective_lobby_capacity():
    """Test effective capacity resolution between explicit max and role limits."""
    # Explicit max_accepted takes precedence
    active_set = {
        "positive": ["tank", "heal"],
        "options": [{"id": "tank", "max_slots": 2}, {"id": "heal", "max_slots": 2}]
    }
    assert effective_lobby_capacity(10, active_set) == 10

    # Role limits sum when max_accepted is 0
    role_limits = {"tank": 3, "heal": 2}
    assert effective_lobby_capacity(0, active_set, role_limits) == 5

    # Uncapped role returns None
    uncapped_active_set = {
        "positive": ["tank", "dps"],
        "options": [{"id": "tank", "max_slots": 2}, {"id": "dps", "max_slots": 0}]
    }
    assert effective_lobby_capacity(0, uncapped_active_set) is None

def test_count_positive_rsvps_and_full_check():
    """Test counting active positive RSVPs excluding waitlist, and full capacity checking."""
    rsvps = [
        {"status": "tank"},
        {"status": "heal"},
        {"status": "wait_tank"},
        {"status": "not_coming"},
    ]
    positive_statuses = ["tank", "heal"]
    count = count_positive_rsvps(rsvps, positive_statuses)
    assert count == 2
    assert lobby_is_full(count, cap=2) is True
    assert lobby_is_full(count, cap=3) is False

def test_role_limits_from_extra_json():
    """Test parsing role limits from JSON string and dict extra_data."""
    extra_str = '{"role_limits": {"tank": 2, "heal": 2}}'
    assert role_limits_from_extra(extra_str) == {"tank": 2, "heal": 2}
    assert role_limits_from_extra(None) == {}
    assert role_limits_from_extra("invalid json string") == {}
