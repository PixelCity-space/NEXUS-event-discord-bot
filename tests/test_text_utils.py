from utils.text_utils import safe_format, slugify


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


def test_safe_format_basic():
    """Test standard placeholder replacement."""
    res = safe_format("Hello {name}, your role is {role}!", name="Alice", role="Tank")
    assert res == "Hello Alice, your role is Tank!"


def test_safe_format_missing_and_unknown_placeholders():
    """Test that missing placeholders are kept intact without throwing KeyError (DoS prevention)."""
    res = safe_format("Event: {title}, Starts: {date}, Note: {unknown}", title="Raid Night")
    assert res == "Event: Raid Night, Starts: {date}, Note: {unknown}"


def test_safe_format_malformed_braces():
    """Test that malformed or single braces do not crash the engine with ValueError."""
    res = safe_format("Unclosed { brace and {title} } ending", title="Mythic")
    assert res == "Unclosed { brace and Mythic } ending"


def test_safe_format_introspection_attack_prevention():
    """Test that Python object introspection patterns like .__class__ are ignored and never evaluated."""
    res = safe_format("Testing {title.__class__} and {title}", title="SafeString")
    assert res == "Testing {title.__class__} and SafeString"


def test_safe_format_edge_cases():
    """Test None, empty strings, numbers, and None kwarg values."""
    assert safe_format(None) == ""
    assert safe_format("") == ""
    assert safe_format(123) == "123"
    assert safe_format("No placeholders") == "No placeholders"
    assert safe_format("Val: {val}", val=None) == "Val: "
    assert safe_format("Val: {num}", num=42) == "Val: 42"
