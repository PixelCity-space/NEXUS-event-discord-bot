import logging
from utils.logger import GuildLoggerAdapter, set_log_level, log

def test_guild_logger_adapter_global_prefix():
    """Test log prefix defaults to [Global] when guild_id is not provided."""
    dummy_logger = logging.getLogger("test_logger_global")
    adapter = GuildLoggerAdapter(dummy_logger, {"guild_id": None})
    msg, kwargs = adapter.process("Hello world", {})
    assert msg == "[Global] Hello world"

def test_guild_logger_adapter_guild_prefix():
    """Test log prefix includes [Guild: <id>] when passed in extra or kwargs."""
    dummy_logger = logging.getLogger("test_logger_guild")
    adapter = GuildLoggerAdapter(dummy_logger, {"guild_id": None})
    msg, kwargs = adapter.process("Event created", {"guild_id": "123456789"})
    assert msg == "[Guild: 123456789] Event created"
    assert "guild_id" not in kwargs

def test_set_log_level():
    """Test dynamic log level switching."""
    set_log_level("DEBUG")
    assert log.logger.level == logging.DEBUG

    set_log_level("WARNING")
    assert log.logger.level == logging.WARNING

    set_log_level("INFO")
    assert log.logger.level == logging.INFO
