from utils.i18n import ALL_MESSAGES, GUILD_CACHE, t


def test_t_none_returns_empty():
    """Test translating None key returns an empty string."""
    assert t(None) == ""

def test_t_missing_key_returns_key_itself():
    """Test missing translation key returns the raw key name."""
    assert t("NON_EXISTENT_KEY_99999") == "NON_EXISTENT_KEY_99999"

def test_t_formatting_kwargs():
    """Test string template substitution with kwargs."""
    # Temporarily populate ALL_MESSAGES for testing
    ALL_MESSAGES.setdefault("en", {})["TEST_GREETING"] = "Hello, {user}! Welcome to {place}."
    try:
        rendered = t("TEST_GREETING", user="NexusBot", place="Discord")
        assert rendered == "Hello, NexusBot! Welcome to Discord."
    finally:
        ALL_MESSAGES.get("en", {}).pop("TEST_GREETING", None)

def test_t_guild_override_cache():
    """Test that guild overrides take highest priority."""
    guild_id = "test_guild_123"
    GUILD_CACHE[guild_id] = {
        "overrides": {"TEST_CUSTOM_MSG": "Custom Guild Message {role}"},
        "settings": {},
        "lang": "en",
    }
    try:
        res = t("TEST_CUSTOM_MSG", guild_id=guild_id, role="Moderator")
        assert res == "Custom Guild Message Moderator"
    finally:
        GUILD_CACHE.pop(guild_id, None)
