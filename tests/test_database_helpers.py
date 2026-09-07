from database.repositories.events import (
    normalize_image_urls_for_store,
    normalize_rsvp_allowed_role_ids_value,
)


def test_normalize_rsvp_allowed_role_ids_value_valid():
    """Test extracting and deduplicating comma-separated numeric role IDs."""
    raw = "123456, 789012, 123456"
    assert normalize_rsvp_allowed_role_ids_value(raw) == "123456,789012"

def test_normalize_rsvp_allowed_role_ids_value_empty():
    """Test that None, empty strings, and whitespace return an empty string."""
    assert normalize_rsvp_allowed_role_ids_value(None) == ""
    assert normalize_rsvp_allowed_role_ids_value("") == ""
    assert normalize_rsvp_allowed_role_ids_value("   ") == ""
    assert normalize_rsvp_allowed_role_ids_value(",,,") == ""

def test_normalize_rsvp_allowed_role_ids_value_mixed_symbols():
    """Test cleaning role mentions and non-digit characters."""
    raw = "<@&112233>, <@&445566>, abc"
    assert normalize_rsvp_allowed_role_ids_value(raw) == "112233,445566"

def test_normalize_image_urls_for_store_list():
    """Test normalizing a list of image URLs into a comma-separated string."""
    images = ["https://example.com/1.png", "  https://example.com/2.png  ", ""]
    assert normalize_image_urls_for_store(images) == "https://example.com/1.png,https://example.com/2.png"

def test_normalize_image_urls_for_store_str_and_empty():
    """Test string URL cleaning and empty values returning None."""
    assert normalize_image_urls_for_store("https://example.com/banner.jpg") == "https://example.com/banner.jpg"
    assert normalize_image_urls_for_store("") is None
    assert normalize_image_urls_for_store([]) is None
    assert normalize_image_urls_for_store(None) is None
