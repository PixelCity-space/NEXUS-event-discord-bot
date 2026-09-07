import discord
import pytest

from utils.emoji_utils import (
    parse_emoji_config,
    resolve_placeholders,
    split_emoji,
    to_emoji,
)


def test_parse_emoji_config_valid():
    """Test parsing multi-line emoji configuration strings with flags and limits."""
    raw_config = """
    🛡️ | Tank | Tanks | 2 | SPEG
    💉 | Healer | Healers | 2 | SPER
    ⚔️ | DPS | Damage Dealers | 4 | SPEB
    ❓ | Maybe | Tentative | 0 | SEY
    """
    options, pos_count = parse_emoji_config(raw_config)
    assert len(options) == 4
    assert pos_count == 3  # Tank, Healer, DPS have 'P' flag

    tank_opt = options[0]
    assert tank_opt["id"] == "tank"
    assert tank_opt["emoji"] == "🛡️"
    assert tank_opt["label"] == "Tank"
    assert tank_opt["list_label"] == "Tanks"
    assert tank_opt["max_slots"] == 2
    assert tank_opt["positive"] is True
    assert tank_opt["button_color"] == "success" # 'G' -> success

    dps_opt = options[2]
    assert dps_opt["button_color"] == "primary" # 'B' -> primary

def test_parse_emoji_config_invalid():
    """Test error handling when emoji configuration line has insufficient columns."""
    invalid_config = "JustOneColumn"
    with pytest.raises(ValueError, match="Too few columns"):
        parse_emoji_config(invalid_config)

def test_split_emoji_custom_and_unicode():
    """Test splitting custom Discord emoji and unicode emojis from button labels."""
    # Custom Discord emoji
    custom_label = "<:nexus_tank:1234567890> Tank Role"
    emoji_obj, clean_label = split_emoji(custom_label)
    assert isinstance(emoji_obj, discord.PartialEmoji)
    assert clean_label == "Tank Role"

    # Unicode emoji
    unicode_label = "✅ Accept Event"
    u_emoji, u_clean = split_emoji(unicode_label)
    assert u_emoji == "✅"
    assert u_clean == "Accept Event"

    # Plain text without emoji
    p_emoji, p_clean = split_emoji("No Emoji Here")
    assert p_emoji is None
    assert p_clean == "No Emoji Here"

def test_to_emoji_and_placeholders():
    """Test to_emoji string converter and placeholder resolver."""
    # None or empty
    assert to_emoji(None) is None
    assert to_emoji("") is None

    # Discord custom emoji string
    custom_str = "<a:party_blob:987654321>"
    res = to_emoji(custom_str)
    assert isinstance(res, discord.PartialEmoji)

    # Standard string
    assert to_emoji("⭐") == "⭐"

    # resolve_placeholders on text with no placeholders
    assert resolve_placeholders("Hello World") == "Hello World"
    assert resolve_placeholders(None) == ""
