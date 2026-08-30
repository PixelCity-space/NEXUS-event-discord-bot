from utils.emojis import (
    get_all_emojis,
    SUCCESS,
    ERROR,
    WARNING,
    INFO,
    TEMP_STD_YES,
    TEMP_MMO_TANK,
    TEMP_SURVEY_LIKE,
)
from utils.emoji_utils import resolve_placeholders

def test_get_all_emojis_returns_dict():
    """Test get_all_emojis returns all uppercase emoji constants as a dictionary."""
    emojis = get_all_emojis()
    assert isinstance(emojis, dict)
    assert len(emojis) > 10
    assert all(k.isupper() for k in emojis.keys())

def test_core_emojis_present():
    """Test core status emojis are present in registry."""
    emojis = get_all_emojis()
    assert emojis["SUCCESS"] == SUCCESS
    assert emojis["ERROR"] == ERROR
    assert emojis["WARNING"] == WARNING
    assert emojis["INFO"] == INFO

def test_template_emojis_present():
    """Test template-specific emojis are present in registry."""
    emojis = get_all_emojis()
    assert emojis["TEMP_STD_YES"] == TEMP_STD_YES
    assert emojis["TEMP_MMO_TANK"] == TEMP_MMO_TANK
    assert emojis["TEMP_SURVEY_LIKE"] == TEMP_SURVEY_LIKE

def test_resolve_placeholders_with_registry():
    """Test replacing {SUCCESS} and {ERROR} placeholders with their Discord emojis."""
    raw = "Operation result: {SUCCESS} completed, {ERROR} failed."
    resolved = resolve_placeholders(raw)
    assert SUCCESS in resolved
    assert ERROR in resolved
    assert "{SUCCESS}" not in resolved

def test_resolve_placeholders_unknown_left_intact():
    """Test unknown placeholders are preserved as-is without raising exceptions."""
    raw = "Test {UNKNOWN_PLACEHOLDER_999} text"
    resolved = resolve_placeholders(raw)
    assert "{UNKNOWN_PLACEHOLDER_999}" in resolved
