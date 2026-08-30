import pytest
from utils.text_utils import slugify

def test_slugify_basic():
    """Test standard alphanumeric text slugification."""
    assert slugify("Hello World") == "hello_world"
    assert slugify("Event 2026 Test") == "event_2026_test"

def test_slugify_accents_and_special_chars():
    """Test removing accents (e.g., Hungarian) and special punctuation characters."""
    assert slugify("Árvíztűrő Tükörfúrógép") == "arvizturo_tukorfurogep"
    assert slugify("Raid: Tank & Heal (v2.0)!") == "raid_tank_heal_v2_0"

def test_slugify_custom_separator():
    """Test slugification with custom separator like hyphen."""
    assert slugify("Custom Separator Test", separator="-") == "custom-separator-test"
    assert slugify("  Multiple   Spaces  ", separator="-") == "multiple-spaces"

def test_slugify_none_and_empty():
    """Test handling of None, empty strings, and non-string types."""
    assert slugify(None) == ""
    assert slugify("") == ""
    assert slugify("   ") == ""
    assert slugify(12345) == "12345"
