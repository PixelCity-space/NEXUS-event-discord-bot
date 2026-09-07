from unittest.mock import AsyncMock, MagicMock

import pytest

from database.repositories.events import (
    normalize_image_urls_for_store,
    normalize_rsvp_allowed_role_ids_value,
)
from database.repositories.reminders import normalize_reminders_for_store
from services.notification_service import send_event_alert
from utils.calendar_utils import generate_ics_batch
from utils.i18n import ALL_MESSAGES, GUILD_CACHE, t
from utils.templates import ICON_SET_TEMPLATES, get_template_data


def test_integration_i18n_template_language_setting_priority():
    """Integration: template_language setting switches button translations while keeping general language."""
    guild_id = "test_guild_multi_lang"
    ALL_MESSAGES.setdefault("hu", {})["BTN_ACCEPT"] = "Részt veszek"
    ALL_MESSAGES.setdefault("en", {})["BTN_ACCEPT"] = "I'm coming"

    # Guild configured with general lang = hu, template_language = en
    GUILD_CACHE[guild_id] = {
        "overrides": {},
        "settings": {"language": "hu", "template_language": "en"},
        "lang": "hu",
    }
    try:
        # General message uses hu
        general_btn = t("BTN_ACCEPT", guild_id=guild_id, use_template_lang=False)
        assert general_btn == "Részt veszek"

        # Template button uses en
        template_btn = t("BTN_ACCEPT", guild_id=guild_id, use_template_lang=True)
        assert template_btn == "I'm coming"
    finally:
        GUILD_CACHE.pop(guild_id, None)

def test_integration_template_data_all_standard_templates():
    """Integration: Verify data integrity, button limits, and positive counts across all standard icon sets."""
    for tmpl_id in ICON_SET_TEMPLATES.keys():
        data = get_template_data(tmpl_id)
        assert data is not None
        assert "options" in data
        assert len(data["options"]) > 0
        assert "positive_count" in data
        assert data["positive_count"] >= 0
        assert "buttons_per_row" in data
        assert 1 <= data["buttons_per_row"] <= 5

def test_integration_full_ics_export_with_custom_recurrence():
    """Integration: Batch ICS generation correctly calculates and outputs multi-event series."""
    event = {
        "event_id": "EVT-CUSTOM-REC",
        "title": "Guild Arena Night",
        "description": "Weekly PvP tournament",
        "start_time": 1780000000.0,
        "end_time": 1780007200.0,
        "recurrence_type": "custom",
        "custom_days": "0, 2, 4", # Mon, Wed, Fri
        "timezone": "UTC",
    }
    ics_text = generate_ics_batch([event], limit_days=14, max_occurrences=4)
    assert "BEGIN:VCALENDAR" in ics_text
    assert ics_text.count("BEGIN:VEVENT") >= 2
    assert "SUMMARY:Guild Arena Night" in ics_text
    assert "END:VCALENDAR" in ics_text

@pytest.mark.asyncio
async def test_integration_discord_message_splitting_and_formatting():
    """Integration: High participant count (>50) is safely capped at max_pings without overflowing."""
    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    # 100 user IDs
    user_ids = list(range(1000, 1100))
    stats = await send_event_alert(
        bot=bot,
        channel_id=12345,
        target_user_ids=user_ids,
        method="ping",
        content="Community event starting!",
        max_pings=50,
    )
    assert stats["channel_sent"] == 1
    mock_channel.send.assert_called_once()
    sent_content = mock_channel.send.call_args.kwargs["content"]
    assert "<@1000>" in sent_content
    assert "<@1049>" in sent_content
    # User 50+ should not be pinged to avoid Discord char/mention limit
    assert "<@1050>" not in sent_content

def test_integration_event_wizard_data_validation_and_normalization():
    """Integration: Full pipeline of raw wizard input normalization and validation."""
    raw_wizard_input = {
        "title": "  Epic Raid   ",
        "rsvp_allowed_role_ids": "<@&111222>, <@&333444>, <@&111222>",
        "image_urls": ["  https://example.com/banner.png  ", ""],
        "reminder_offsets": ["1d,dm,coming", "15m"],
        "reminder_messages": ["Tomorrow's raid!", None],
    }

    cleaned_roles = normalize_rsvp_allowed_role_ids_value(raw_wizard_input["rsvp_allowed_role_ids"])
    cleaned_images = normalize_image_urls_for_store(raw_wizard_input["image_urls"])
    cleaned_reminders = normalize_reminders_for_store(raw_wizard_input)

    assert cleaned_roles == "111222,333444"
    assert cleaned_images == "https://example.com/banner.png"
    assert len(cleaned_reminders) == 2
    assert cleaned_reminders[0]["offset_str"] == "1d"
    assert cleaned_reminders[0]["method"] == "dm"
    assert cleaned_reminders[1]["offset_str"] == "15m"
    assert cleaned_reminders[1]["method"] == "ping"
