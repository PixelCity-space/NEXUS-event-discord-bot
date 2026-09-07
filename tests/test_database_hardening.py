import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

import database
from main import EventBot


@pytest.fixture
def mock_pool():
    pool = MagicMock(spec=asyncpg.Pool)
    conn = MagicMock(spec=asyncpg.Connection)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)

    class AcquireContext:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class TxContext:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    pool.acquire.return_value = AcquireContext()
    conn.transaction.return_value = TxContext()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetchval = AsyncMock(return_value=None)
    pool.close = AsyncMock()
    return pool, conn


@pytest.mark.asyncio
async def test_database_create_pool_tuned_defaults():
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_asyncpg_pool:
        mock_asyncpg_pool.return_value = MagicMock()
        pool = await database.create_pool("postgresql://user:pass@localhost/db")
        assert pool is not None
        mock_asyncpg_pool.assert_called_once_with(
            "postgresql://user:pass@localhost/db",
            min_size=5,
            max_size=20,
            command_timeout=30.0,
            max_inactive_connection_lifetime=300.0,
            timeout=10.0,
        )


@pytest.mark.asyncio
async def test_main_init_database_pool_env_overrides():
    bot = EventBot()
    env_vars = {
        "DATABASE_URL": "postgresql://user:pass@localhost/testdb",
        "DB_POOL_MIN_SIZE": "8",
        "DB_POOL_MAX_SIZE": "40",
        "DB_COMMAND_TIMEOUT": "45.0",
        "DB_MAX_INACTIVE_LIFETIME": "600.0",
        "DB_ACQUIRE_TIMEOUT": "15.0",
    }
    with patch.dict(os.environ, env_vars), \
         patch("database.create_pool", new_callable=AsyncMock) as mock_db_pool, \
         patch("database.set_pool", new_callable=AsyncMock), \
         patch("database.init_db", new_callable=AsyncMock), \
         patch("main.load_guild_translations", new_callable=AsyncMock), \
         patch("database.get_all_global_emoji_sets", new_callable=AsyncMock, return_value=[{"set_id": "std"}]):

        mock_pool = MagicMock()
        mock_db_pool.return_value = mock_pool

        await bot._init_database()

        mock_db_pool.assert_called_once_with(
            "postgresql://user:pass@localhost/testdb",
            min_size=8,
            max_size=40,
            command_timeout=45.0,
            max_inactive_connection_lifetime=600.0,
            timeout=15.0,
        )
        assert bot.db_pool == mock_pool


@pytest.mark.asyncio
async def test_save_global_emoji_set_jsonb_handling(mock_pool):
    pool, _ = mock_pool
    database.db_manager.set_pool(pool)

    # 1. Dict data -> serialized to JSON
    dict_data = {"1": "🔥", "2": "⚔️"}
    await database.save_global_emoji_set("custom_combat", "Combat", dict_data)
    args = pool.execute.call_args[0]
    assert args[1] == "custom_combat"
    assert args[2] == "Combat"
    assert json.loads(args[3]) == dict_data

    # 2. Valid JSON string -> preserved as JSON
    json_str = '{"1": "🛡️"}'
    await database.save_global_emoji_set("custom_defense", "Defense", json_str)
    args = pool.execute.call_args[0]
    assert args[1] == "custom_defense"
    assert json.loads(args[3]) == {"1": "🛡️"}

    # 3. Plain text / primitive string -> json encoded
    raw_str = "simple_string"
    await database.save_global_emoji_set("custom_raw", "Raw", raw_str)
    args = pool.execute.call_args[0]
    assert args[1] == "custom_raw"
    assert json.loads(args[3]) == "simple_string"


@pytest.mark.asyncio
async def test_migration_002_file_exists_and_valid():
    migrations_dir = database.connection.MIGRATIONS_DIR
    mig_002 = migrations_dir / "002_cascade_foreign_keys_and_types.sql"
    assert mig_002.exists()
    content = mig_002.read_text(encoding="utf-8")
    assert "fk_rsvps_active_events" in content
    assert "fk_event_reminders_active_events" in content
    assert "ON DELETE CASCADE" in content
    assert "global_emoji_sets" in content
