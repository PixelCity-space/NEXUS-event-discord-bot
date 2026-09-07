import json

from utils.extra_data import EventExtraData, parse_extra_data, serialize_extra_data


def test_event_extra_data_defaults():
    dto = EventExtraData()
    assert dto.role_limits == {}
    assert dto.waiting_list_limit is None
    assert dto.lobby_auto_start_offset is None
    assert dto.custom_promo_msg is None
    assert dto.custom_reminder_msg is None
    assert dto.thread_id is None
    assert dto.recurrence_limit_date is None
    assert dto.extra_fields == {}
    assert dto.to_dict() == {}
    assert dto.to_json() == "{}"


def test_from_raw_none_and_empty():
    assert parse_extra_data(None).to_dict() == {}
    assert parse_extra_data("").to_dict() == {}
    assert parse_extra_data("   ").to_dict() == {}
    assert parse_extra_data("{}").to_dict() == {}
    assert parse_extra_data(12345).to_dict() == {}  # Invalid type fallback


def test_from_raw_invalid_json():
    corrupt_json = "{ invalid_json: True, "
    dto = parse_extra_data(corrupt_json)
    assert isinstance(dto, EventExtraData)
    assert dto.to_dict() == {}


def test_from_raw_valid_json_string():
    raw = json.dumps({
        "role_limits": {"tank": 2, "dps": "4"},
        "waiting_list_limit": "5",
        "lobby_auto_start_offset": "1h",
        "custom_promo_msg": "Congrats {user_id}!",
        "custom_reminder_msg": "Reminder for {event}!",
        "thread_id": "987654321",
        "recurrence_limit_date": "1700000000",
        "custom_custom_field": "val123"
    })
    dto = parse_extra_data(raw)
    assert dto.role_limits == {"tank": 2, "dps": 4}
    assert dto.waiting_list_limit == 5
    assert dto.lobby_auto_start_offset == "1h"
    assert dto.custom_promo_msg == "Congrats {user_id}!"
    assert dto.custom_reminder_msg == "Reminder for {event}!"
    assert dto.thread_id == 987654321
    assert dto.recurrence_limit_date == 1700000000
    assert dto.extra_fields == {"custom_custom_field": "val123"}


def test_from_raw_dict():
    data = {
        "role_limits": {"healer": 1},
        "waiting_list_limit": 10,
        "thread_id": 12345,
    }
    dto = parse_extra_data(data)
    assert dto.role_limits == {"healer": 1}
    assert dto.waiting_list_limit == 10
    assert dto.thread_id == 12345
    assert dto.custom_promo_msg is None


def test_from_raw_idempotent_instance():
    dto1 = EventExtraData(role_limits={"tank": 3}, waiting_list_limit=2)
    dto2 = parse_extra_data(dto1)
    assert dto1 is dto2


def test_serialize_extra_data():
    dto = EventExtraData(
        role_limits={"dps": 2},
        waiting_list_limit=3,
        custom_promo_msg="Promo msg"
    )
    serialized = serialize_extra_data(dto)
    assert isinstance(serialized, str)
    parsed = json.loads(serialized)
    assert parsed["role_limits"] == {"dps": 2}
    assert parsed["waiting_list_limit"] == 3
    assert parsed["custom_promo_msg"] == "Promo msg"

    # Test serialization of dict and str
    assert serialize_extra_data({"a": 1}) == '{"a": 1}'
    assert serialize_extra_data('{"b": 2}') == '{"b": 2}'
    assert serialize_extra_data(None) == "{}"
    assert serialize_extra_data("invalid json") == "{}"


def test_dict_like_compatibility():
    dto = EventExtraData.from_raw({
        "role_limits": {"tank": 2},
        "waiting_list_limit": 5,
        "custom_key": "custom_value"
    })
    
    # Test get and __getitem__
    assert dto.get("role_limits") == {"tank": 2}
    assert dto.get("non_existing", "default") == "default"
    assert dto["waiting_list_limit"] == 5
    assert dto["custom_key"] == "custom_value"
    assert "role_limits" in dto
    assert "custom_key" in dto
    assert "missing" not in dto

    # Test __setitem__
    dto["waiting_list_limit"] = 20
    assert dto.waiting_list_limit == 20
    assert dto["waiting_list_limit"] == 20

    dto["role_limits"] = {"mage": 3}
    assert dto.role_limits == {"mage": 3}

    dto["thread_id"] = 999
    assert dto.thread_id == 999

    dto["custom_promo_msg"] = "Updated promo"
    assert dto.custom_promo_msg == "Updated promo"

    dto["new_custom_field"] = "hello"
    assert dto.extra_fields["new_custom_field"] == "hello"
    assert dto["new_custom_field"] == "hello"
