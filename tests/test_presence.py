import time
from unittest.mock import AsyncMock, patch

import pytest

from utils.presence import (
    _config_cache,
    _get_cached_presence_config,
    _get_cached_stats,
    _stats_cache,
)


@pytest.mark.asyncio
async def test_stats_cache_ttl():
    """Test _get_cached_stats uses memory cache until TTL expires."""
    _stats_cache["data"] = {"events": 42, "guilds": 10, "rsvps": 100}
    _stats_cache["expires_at"] = time.time() + 300.0

    with patch("database.get_global_stats", new_callable=AsyncMock) as mock_db:
        stats = await _get_cached_stats()
        assert stats == {"events": 42, "guilds": 10, "rsvps": 100}
        mock_db.assert_not_called()

@pytest.mark.asyncio
async def test_stats_cache_expired_fetches_db():
    """Test _get_cached_stats queries database when cache is expired."""
    _stats_cache["expires_at"] = time.time() - 10.0 # Expired

    with patch("database.get_global_stats", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = {"events": 15, "guilds": 3, "rsvps": 50}
        stats = await _get_cached_stats()
        assert stats == {"events": 15, "guilds": 3, "rsvps": 50}
        mock_db.assert_called_once()

@pytest.mark.asyncio
async def test_cached_presence_config_defaults():
    """Test _get_cached_presence_config returns default config when db setting is empty."""
    _config_cache["data"] = None
    _config_cache["expires_at"] = 0.0

    with patch("database.get_global_setting", new_callable=AsyncMock) as mock_setting:
        mock_setting.return_value = None
        config = await _get_cached_presence_config()
        assert config["time"] == 30
        assert config["mode"] == "random"
        assert len(config["statuses"]) == 1

@pytest.mark.asyncio
async def test_cached_presence_config_custom_json():
    """Test _get_cached_presence_config parses custom JSON dict from database."""
    _config_cache["data"] = None
    _config_cache["expires_at"] = 0.0

    custom_json = '{"time": 45, "mode": "sequential", "statuses": [{"type": "playing", "text": "Nexus Bot"}]}'
    with patch("database.get_global_setting", new_callable=AsyncMock) as mock_setting:
        mock_setting.return_value = custom_json
        config = await _get_cached_presence_config()
        assert config["time"] == 45
        assert config["mode"] == "sequential"
        assert config["statuses"][0]["text"] == "Nexus Bot"

@pytest.mark.asyncio
async def test_cached_presence_config_invalid_json():
    """Test _get_cached_presence_config handles corrupt JSON without crashing."""
    _config_cache["data"] = None
    _config_cache["expires_at"] = 0.0

    with patch("database.get_global_setting", new_callable=AsyncMock) as mock_setting:
        mock_setting.return_value = "invalid { json ]"
        config = await _get_cached_presence_config()
        assert config["time"] == 30
        assert config["mode"] == "random"
