import discord

from utils.emoji_utils import make_button, make_select_option


def test_make_select_option_with_custom_emoji():
    """Test creating a discord.SelectOption with auto-extracted custom emoji."""
    raw_label = "<:tank_icon:123456> Main Tank"
    opt = make_select_option(label=raw_label, value="tank_opt")
    assert isinstance(opt, discord.SelectOption)
    assert opt.label == "Main Tank"
    assert isinstance(opt.emoji, discord.PartialEmoji)
    assert opt.value == "tank_opt"

def test_make_select_option_with_unicode_emoji():
    """Test creating a discord.SelectOption with auto-extracted unicode emoji."""
    raw_label = "✅ Attending Event"
    opt = make_select_option(label=raw_label, value="attend_val")
    assert isinstance(opt, discord.SelectOption)
    assert opt.label == "Attending Event"
    assert opt.emoji.name == "✅"

def test_make_button_with_custom_emoji():
    """Test creating a discord.ui.Button with auto-extracted custom emoji."""
    raw_label = "<a:party_blob:789012> Join Party"
    btn = make_button(label=raw_label, custom_id="join_btn")
    assert isinstance(btn, discord.ui.Button)
    assert btn.label == "Join Party"
    assert isinstance(btn.emoji, discord.PartialEmoji)
    assert btn.custom_id == "join_btn"

def test_make_button_override_emoji():
    """Test explicitly supplied emoji overrides the extracted emoji."""
    raw_label = "⭐ Star Event"
    btn = make_button(label=raw_label, emoji="🌟")
    assert btn.label == "Star Event"
    assert btn.emoji.name == "🌟"
