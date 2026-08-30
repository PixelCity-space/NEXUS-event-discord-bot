from unittest.mock import MagicMock
from services.notification_service import resolve_target_recipients

def _sample_active_set():
    return {
        "positive": ["tank", "heal", "dps"],
        "options": [
            {"id": "tank", "label": "Tank", "list_label": "Tanks", "positive": True},
            {"id": "heal", "label": "Healer", "list_label": "Healers", "positive": True},
            {"id": "dps", "label": "Damage", "list_label": "DPS", "positive": True},
            {"id": "not_coming", "label": "Not Coming", "list_label": "Declined", "positive": False},
        ]
    }

def test_resolve_target_recipients_all():
    """Test resolving 'all' targets returns all non-waitlist participants."""
    bot = MagicMock()
    db_event = {"guild_id": 12345}
    active_set = _sample_active_set()
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "heal"},
        {"user_id": 103, "status": "not_coming"},
    ]

    recipients = resolve_target_recipients(bot, db_event, "all", rsvps, active_set)
    assert recipients == [101, 102, 103]

def test_resolve_target_recipients_coming_aliases():
    """Test resolving positive aliases ('coming', 'positive', 'accepted')."""
    bot = MagicMock()
    db_event = {"guild_id": 12345}
    active_set = _sample_active_set()
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "heal"},
        {"user_id": 103, "status": "not_coming"},
    ]

    rec_coming = resolve_target_recipients(bot, db_event, "coming", rsvps, active_set)
    assert rec_coming == [101, 102]

    rec_pos = resolve_target_recipients(bot, db_event, "positive", rsvps, active_set)
    assert rec_pos == [101, 102]

def test_resolve_target_recipients_not_coming():
    """Test resolving negative aliases ('not_coming', 'negative', 'declined')."""
    bot = MagicMock()
    db_event = {"guild_id": 12345}
    active_set = _sample_active_set()
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "not_coming"},
    ]

    rec_not_coming = resolve_target_recipients(bot, db_event, "not_coming", rsvps, active_set)
    assert rec_not_coming == [102]

def test_resolve_target_recipients_by_option_id_or_label():
    """Test resolving specific option ID or label (e.g., 'tank' or 'Healer')."""
    bot = MagicMock()
    db_event = {"guild_id": 12345}
    active_set = _sample_active_set()
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "tank"},
        {"user_id": 103, "status": "heal"},
    ]

    rec_tank = resolve_target_recipients(bot, db_event, "tank", rsvps, active_set)
    assert rec_tank == [101, 102]

    rec_healer = resolve_target_recipients(bot, db_event, "Healer", rsvps, active_set)
    assert rec_healer == [103]

def test_resolve_target_recipients_deduping_and_waitlist():
    """Test that waitlisted entries are ignored and duplicate user IDs are deduplicated."""
    bot = MagicMock()
    db_event = {"guild_id": 12345}
    active_set = _sample_active_set()
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 101, "status": "tank"}, # duplicate
        {"user_id": 104, "status": "wait_tank"}, # waitlisted
    ]

    rec = resolve_target_recipients(bot, db_event, "all", rsvps, active_set)
    assert rec == [101]
