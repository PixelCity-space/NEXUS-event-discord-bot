from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from services.notification_service import resolve_target_recipients, send_event_alert
from utils.emoji_utils import make_button, make_select_option, parse_emoji_config
from utils.emojis import CALENDAR, SUCCESS
from utils.i18n import GUILD_CACHE, t
from utils.templates import get_template_data


@pytest.mark.asyncio
async def test_integration_notification_audience_resolution_to_dispatch():
    """Integration: Resolving audience targets -> formatting ping mentions -> dispatching alert."""
    active_set = get_template_data("mmo")
    rsvps = [
        {"user_id": 101, "status": "tank"},
        {"user_id": 102, "status": "heal"},
        {"user_id": 103, "status": "dps"},
        {"user_id": 104, "status": "not_coming"},
    ]
    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    # 1. Resolve recipients for target 'coming'
    recipients = resolve_target_recipients(bot, {"guild_id": 123}, "coming", rsvps, active_set)
    assert recipients == [101, 102, 103]

    # 2. Dispatch channel alert
    stats = await send_event_alert(
        bot=bot,
        channel_id=98765,
        target_user_ids=recipients,
        method="ping",
        content="Raid group forming now!",
    )
    assert stats["channel_sent"] == 1
    mock_channel.send.assert_called_once()
    sent_content = mock_channel.send.call_args.kwargs["content"]
    assert "<@101>, <@102>, <@103>" in sent_content
    assert "Raid group forming now!" in sent_content

@pytest.mark.asyncio
async def test_integration_temp_role_alert_dispatch():
    """Integration: Dispatching notification using temporary role mention."""
    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    stats = await send_event_alert(
        bot=bot,
        channel_id=98765,
        target_user_ids=[101, 102],
        temp_role_id=888999,
        method="channel",
        content="Event starting!",
    )
    assert stats["channel_sent"] == 1
    sent_content = mock_channel.send.call_args.kwargs["content"]
    assert "<@&888999>" in sent_content

def test_integration_i18n_guild_override_with_placeholders():
    """Integration: Multi-layer translation resolution with guild overrides and emoji placeholders."""
    guild_id = "test_guild_integration"
    GUILD_CACHE[guild_id] = {
        "overrides": {"EVENT_REMINDER_CUSTOM": "{SUCCESS} Reminder: Event '{title}' starts soon! {CALENDAR}"},
        "settings": {},
        "lang": "en",
    }
    try:
        rendered = t("EVENT_REMINDER_CUSTOM", guild_id=guild_id, title="Mythic Vault")
        assert SUCCESS in rendered
        assert CALENDAR in rendered
        assert "Mythic Vault" in rendered
        assert "{SUCCESS}" not in rendered
    finally:
        GUILD_CACHE.pop(guild_id, None)

@pytest.mark.asyncio
async def test_integration_notification_dm_delivery_with_fallback():
    """Integration: Dispatching individual DMs with failure resilience."""
    bot = MagicMock()
    user1 = MagicMock()
    user1.send = AsyncMock()

    user2 = MagicMock()
    user2.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send DM"))

    bot.get_user.side_effect = lambda uid: user1 if uid == 101 else (user2 if uid == 102 else None)

    stats = await send_event_alert(
        bot=bot,
        channel_id=None,
        target_user_ids=[101, 102],
        method="dm",
        content="Your scheduled raid is starting!",
    )
    assert stats["dms_sent"] == 1
    assert stats["dms_failed"] == 1

def test_integration_custom_emoji_wizard_to_template_resolution():
    """Integration: Parsing emoji wizard text format -> rendering UI Discord buttons and select options."""
    wizard_text = """
    🛡️ | Main Tank | Tanks | 2 | SPEG
    💉 | Main Healer | Healers | 2 | SPER
    """
    options, pos_count = parse_emoji_config(wizard_text)
    assert len(options) == 2
    assert pos_count == 2

    # Render select options
    select_opt = make_select_option(label=f"{options[0]['emoji']} {options[0]['label']}", value=options[0]["id"])
    assert select_opt.label == "Main Tank"
    assert select_opt.emoji.name == "🛡️"

    # Render buttons
    btn = make_button(label=f"{options[1]['emoji']} {options[1]['label']}", custom_id=options[1]["id"])
    assert btn.label == "Main Healer"
    assert btn.emoji.name == "💉"
