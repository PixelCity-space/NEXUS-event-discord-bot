import os
from utils.config import Config

def test_config_get_and_defaults():
    """Test Config.get returns default value for missing keys."""
    cfg = Config()
    assert cfg.get("completely_nonexistent_key_123", "default_val") == "default_val"
    assert cfg.get("another_missing_key") is None

def test_config_language_property():
    """Test Config.language defaults or reads environment variable."""
    cfg = Config()
    orig_env = os.environ.get("BOT_LANGUAGE")
    try:
        os.environ["BOT_LANGUAGE"] = "hu"
        assert cfg.language == "hu"
    finally:
        if orig_env is not None:
            os.environ["BOT_LANGUAGE"] = orig_env
        else:
            os.environ.pop("BOT_LANGUAGE", None)

def test_config_command_prefix_env_override():
    """Test Config.command_prefix with environment variable override."""
    cfg = Config()
    orig_env = os.environ.get("COMMAND_PREFIX")
    try:
        os.environ["COMMAND_PREFIX"] = "?"
        assert cfg.command_prefix == "?"
    finally:
        if orig_env is not None:
            os.environ["COMMAND_PREFIX"] = orig_env
        else:
            os.environ.pop("COMMAND_PREFIX", None)

def test_config_premium_guild_ids_env_override():
    """Test Config.premium_guild_ids parsing from comma-separated env var."""
    cfg = Config()
    orig_env = os.environ.get("PREMIUM_GUILD_IDS")
    try:
        os.environ["PREMIUM_GUILD_IDS"] = "111, 222, 333"
        assert cfg.premium_guild_ids == [111, 222, 333]
    finally:
        if orig_env is not None:
            os.environ["PREMIUM_GUILD_IDS"] = orig_env
        else:
            os.environ.pop("PREMIUM_GUILD_IDS", None)
