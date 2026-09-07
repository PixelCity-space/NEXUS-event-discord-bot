import asyncio
from contextlib import asynccontextmanager
import os
import time
from typing import Optional
import asyncpg
import pytest
from database.connection import DatabaseManager, create_pool
from database.repositories import (
    events as event_repo,
    rsvps as rsvp_repo,
    emojis as emoji_repo,
    reminders as reminder_repo,
    settings as settings_repo,
)
from utils.enums import EventStatus


def get_real_postgres_uri() -> Optional[str]:
    """Retrieves the PostgreSQL URI from test environment variables."""
    return os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_URI") or os.getenv("DATABASE_URL")


async def can_connect_postgres(uri: str) -> bool:
    """Probes if the PostgreSQL instance is live, reachable, and accepts credentials."""
    try:
        conn = await asyncio.wait_for(asyncpg.connect(uri), timeout=2.0)
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False


@asynccontextmanager
async def real_db_context():
    """
    Initializes a real DatabaseManager and connection pool against PostgreSQL.
    Skips tests gracefully if no live database instance is reachable.
    """
    uri = get_real_postgres_uri()
    if not uri:
        pytest.skip("No PostgreSQL URI provided (set TEST_DATABASE_URL or POSTGRES_TEST_URI)")

    is_live = await can_connect_postgres(uri)
    if not is_live:
        pytest.skip(f"PostgreSQL database at {uri} is not reachable or authentication failed")

    # Connect and initialize pool
    pool = await create_pool(uri, min_size=2, max_size=10)
    manager = DatabaseManager(pool=pool)

    # Run real migrations
    await manager.run_migrations()

    # Patch global database manager for repository calls
    import database
    orig_manager = database.db_manager
    database.db_manager = manager

    try:
        yield manager
    finally:
        # Teardown & cleanup
        try:
            async with manager.acquire() as conn:
                # Clean up test records
                await conn.execute("DELETE FROM active_events WHERE event_id LIKE 'TEST-PG-%'")
                await conn.execute("DELETE FROM global_emoji_sets WHERE set_id LIKE 'test_pg_%'")
                await conn.execute("DELETE FROM guild_settings WHERE guild_id = '999999999'")
        except Exception:
            pass

        database.db_manager = orig_manager
        await manager.close()


@pytest.mark.asyncio
async def test_real_postgres_migrations_and_schema():
    """Verifies that all migrations (001, 002) applied successfully with valid schema."""
    async with real_db_context() as real_db_manager:
        async with real_db_manager.acquire() as conn:
            # 1. Verify schema_migrations
            rows = await conn.fetch("SELECT version, name FROM schema_migrations ORDER BY version ASC")
            versions = [r["version"] for r in rows]
            assert 1 in versions
            assert 2 in versions

            # 2. Verify tables exist
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_names = {r["table_name"] for r in tables}
            assert "active_events" in table_names
            assert "rsvps" in table_names
            assert "event_reminders" in table_names
            assert "global_emoji_sets" in table_names
            assert "guild_settings" in table_names

            # 3. Verify JSONB data type on global_emoji_sets.data
            col_type = await conn.fetchval("""
                SELECT data_type FROM information_schema.columns 
                WHERE table_name = 'global_emoji_sets' AND column_name = 'data'
            """)
            assert col_type.lower() == "jsonb"


@pytest.mark.asyncio
async def test_real_postgres_cascade_foreign_keys():
    """Verifies ON DELETE CASCADE constraint on rsvps and event_reminders."""
    async with real_db_context() as real_db_manager:
        event_id = f"TEST-PG-CASCADE-{int(time.time())}"
        guild_id = "999999999"

        # 1. Create active event
        await event_repo.create_active_event({
            "event_id": event_id,
            "guild_id": guild_id,
            "title": "Postgres Real Cascade Test",
            "status": EventStatus.ACTIVE.value,
            "start_time": time.time() + 3600,
            "max_accepted": 5,
            "reminder_type": "dm",
        })

        # 2. Add RSVP and Reminders
        await rsvp_repo.join_or_update_rsvp_atomic(
            event_id=event_id,
            user_id=111111,
            requested_status="accepted",
            now=time.time(),
            max_accepted=5,
        )

        slots = [
            {"offset_str": "1h", "method": "dm", "target": "coming", "custom_message": "Cascade test msg"},
            {"offset_str": "15m", "method": "ping", "target": "all", "custom_message": None},
        ]
        await reminder_repo.replace_event_reminders(event_id, slots)

        # Verify records exist
        rsvps_before = await rsvp_repo.get_rsvps(event_id)
        reminders_before = await reminder_repo.get_event_reminders(event_id)
        assert len(rsvps_before) == 1
        assert len(reminders_before) == 2

        # 3. Delete event from active_events
        async with real_db_manager.acquire() as conn:
            await conn.execute("DELETE FROM active_events WHERE event_id = $1", event_id)

        # 4. Verify ON DELETE CASCADE automatically purged rsvps and reminders without orphans
        rsvps_after = await rsvp_repo.get_rsvps(event_id)
        reminders_after = await reminder_repo.get_event_reminders(event_id)
        assert len(rsvps_after) == 0
        assert len(reminders_after) == 0


@pytest.mark.asyncio
async def test_real_postgres_atomic_rsvp_for_update_concurrency():
    """
    Verifies that join_or_update_rsvp_atomic with SELECT ... FOR UPDATE
    prevents overbooking under real concurrent database transactions.
    """
    async with real_db_context() as real_db_manager:
        event_id = f"TEST-PG-RACE-{int(time.time())}"
        guild_id = "999999999"
        max_cap = 3

        # Create event with capacity 3
        await event_repo.create_active_event({
            "event_id": event_id,
            "guild_id": guild_id,
            "title": "Postgres Concurrency Test",
            "status": EventStatus.ACTIVE.value,
            "start_time": time.time() + 7200,
            "max_accepted": max_cap,
        })

        # Spawn 6 concurrent RSVP requests for 3 slots
        now = time.time()
        user_ids = [200001, 200002, 200003, 200004, 200005, 200006]

        async def _join(uid: int):
            return await rsvp_repo.join_or_update_rsvp_atomic(
                event_id=event_id,
                user_id=uid,
                requested_status="accepted",
                now=now,
                max_accepted=max_cap,
            )

        results = await asyncio.gather(*[_join(uid) for uid in user_ids])

        # Count final statuses from results
        accepted_results = [r for r in results if r["final_status"] == "accepted"]
        waiting_results = [r for r in results if r["final_status"] == "wait_accepted"]

        # Verify exact capacity enforcement
        assert len(accepted_results) == 3
        assert len(waiting_results) == 3

        # Verify directly from database table
        rsvps = await rsvp_repo.get_rsvps(event_id)
        db_accepted = [u for u, s in rsvps.items() if s == "accepted"]
        db_waiting = [u for u, s in rsvps.items() if s == "wait_accepted"]

        assert len(db_accepted) == 3
        assert len(db_waiting) == 3

        # Clean up
        async with real_db_manager.acquire() as conn:
            await conn.execute("DELETE FROM active_events WHERE event_id = $1", event_id)


@pytest.mark.asyncio
async def test_real_postgres_jsonb_emoji_and_settings():
    """Verifies real PostgreSQL JSONB storage and querying for emoji sets and settings."""
    async with real_db_context():
        set_id = f"test_pg_emojis_{int(time.time())}"
        payload = {
            "tank": {"emoji": "🛡️", "label": "Main Tank", "limit": 2},
            "healer": {"emoji": "💚", "label": "Resto Healer", "limit": 2},
            "dps": {"emoji": "⚔️", "label": "Damage Dealer", "limit": 6},
        }

        # Save JSONB emoji set
        await emoji_repo.save_global_emoji_set(set_id, "Real Postgres Test Set", payload)

        # Fetch back and assert JSONB deserialization
        sets = await emoji_repo.get_all_global_emoji_sets()
        matching = next((s for s in sets if s["set_id"] == set_id), None)
        assert matching is not None
        assert matching["name"] == "Real Postgres Test Set"
        assert isinstance(matching["data"], dict)
        assert matching["data"]["tank"]["emoji"] == "🛡️"

        # Verify settings repository
        await settings_repo.set_guild_setting("999999999", "theme_color", "#ffaa00")
        val = await settings_repo.get_guild_setting("999999999", "theme_color", default="default")
        assert val == "#ffaa00"

        # Verify global stats aggregation
        stats = await settings_repo.get_global_stats()
        assert isinstance(stats, dict)
        assert "events" in stats
        assert "rsvps" in stats
        assert "guilds" in stats
