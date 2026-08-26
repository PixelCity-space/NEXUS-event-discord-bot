from typing import Optional
import json
import asyncpg
from utils.logger import log

_pool: Optional[asyncpg.Pool] = None
DEFAULT_TIMEZONE: str = 'UTC'
MAX_EVENT_REMINDERS: int = 5

async def set_pool(pool: asyncpg.Pool) -> None:
    """Assigns the global database connection pool."""
    global _pool
    _pool = pool

async def get_pool() -> asyncpg.Pool:
    """Returns the initialized database connection pool."""
    global _pool
    if not _pool:
        raise Exception("Database pool is not initialized.")
    return _pool

async def _migrate_legacy_reminders(conn: asyncpg.Connection) -> None:
    """Migrates legacy reminder fields into the event_reminders table."""
    await conn.execute("""
        INSERT INTO event_reminders (event_id, slot_idx, offset_str, sent)
        SELECT event_id, 0,
               COALESCE(NULLIF(TRIM(reminder_offset), ''), '15m'),
               COALESCE(reminder_sent, 0)
        FROM active_events ae
        WHERE COALESCE(NULLIF(TRIM(reminder_type), ''), 'none') <> 'none'
        AND NOT EXISTS (SELECT 1 FROM event_reminders er WHERE er.event_id = ae.event_id)
    """)
    rows = await conn.fetch(
        "SELECT event_id, extra_data FROM active_events WHERE extra_data IS NOT NULL AND LENGTH(TRIM(extra_data)) > 0"
    )
    for r in rows:
        eid = r["event_id"]
        raw = r["extra_data"]
        try:
            ed = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(ed, dict):
                continue
            msg = (ed.get("custom_reminder_msg") or "").strip()
            if not msg:
                continue
            await conn.execute(
                """
                UPDATE active_events SET reminder_message = $1
                WHERE event_id = $2 AND (reminder_message IS NULL OR LENGTH(TRIM(reminder_message)) = 0)
                """,
                msg,
                eid,
            )
        except Exception as e:
            log.debug("migrate reminder_message %s: %s", eid, e)

async def init_db() -> None:
    """Initializes all PostgreSQL tables, indexes, and applies schema migrations."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Table for active and scheduled events
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS active_events (
                event_id TEXT PRIMARY KEY,
                config_name TEXT,
                message_id BIGINT,
                channel_id BIGINT,
                start_time DOUBLE PRECISION,
                status TEXT DEFAULT 'active',
                title TEXT,
                description TEXT,
                image_urls TEXT,
                color TEXT,
                max_accepted INTEGER,
                ping_role BIGINT,
                end_time DOUBLE PRECISION,
                recurrence_type TEXT,
                repost_trigger TEXT,
                repost_offset TEXT,
                timezone TEXT DEFAULT 'Europe/Budapest',
                creator_id TEXT,
                reminder_type TEXT DEFAULT 'none',
                reminder_offset TEXT DEFAULT '15m',
                reminder_sent INTEGER DEFAULT 0,
                recurrence_limit INTEGER DEFAULT 0,
                recurrence_count INTEGER DEFAULT 0,
                icon_set TEXT DEFAULT 'standard',
                extra_data TEXT,
                guild_id TEXT,
                temp_role_id BIGINT,
                use_temp_role BOOLEAN DEFAULT FALSE
            )
        """)
        
        for stmt in (
            "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS temp_role_id BIGINT",
            "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS use_temp_role BOOLEAN DEFAULT FALSE",
        ):
            try:
                await conn.execute(stmt)
            except Exception as e:
                log.debug("init_db optional ALTER skipped: %s", e)
        
        # Table for event signups (RSVPs) and attendance
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rsvps (
                event_id TEXT,
                user_id BIGINT,
                status TEXT,
                joined_at DOUBLE PRECISION,
                attendance TEXT DEFAULT 'present',
                PRIMARY KEY (event_id, user_id)
            )
        """)

        # Table for saving unfinished event drafts
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS event_drafts (
                draft_id TEXT PRIMARY KEY,
                creator_id TEXT,
                title TEXT,
                data JSONB,
                updated_at DOUBLE PRECISION,
                guild_id TEXT
            )
        """)

        # Table for custom emoji sets per guild
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_emoji_sets (
                guild_id TEXT,
                set_id TEXT,
                name TEXT,
                data JSONB,
                PRIMARY KEY (guild_id, set_id)
            )
        """)

        # Table for per-guild translation string overrides
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_translations (
                guild_id TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)

        # Table for per-guild configuration and defaults
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (guild_id, key)
            )
        """)

        # Table for global bot settings (Master Admin only)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Table for multiple reminder offsets per event
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS event_reminders (
                event_id TEXT NOT NULL,
                slot_idx SMALLINT NOT NULL,
                offset_str TEXT NOT NULL,
                method TEXT,
                custom_message TEXT,
                sent INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (event_id, slot_idx),
                CHECK (slot_idx >= 0 AND slot_idx < 5)
            )
        """)

        for col_name, dt in [("method", "TEXT"), ("custom_message", "TEXT"), ("target", "TEXT DEFAULT 'coming'")]:
            try:
                await conn.execute(f"ALTER TABLE event_reminders ADD COLUMN IF NOT EXISTS {col_name} {dt}")
            except Exception as e:
                log.debug(f"init_db event_reminders {col_name} column: {e}")

        try:
            await conn.execute(
                "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS reminder_message TEXT"
            )
        except Exception as e:
            log.debug("init_db reminder_message column: %s", e)

        try:
            await conn.execute(
                "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS rsvp_allowed_role_ids TEXT DEFAULT ''"
            )
        except Exception as e:
            log.debug("init_db rsvp_allowed_role_ids column: %s", e)

        for lobby_sql in (
            "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS lobby_mode BOOLEAN DEFAULT FALSE",
            "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS lobby_expires_at DOUBLE PRECISION",
            "ALTER TABLE active_events ADD COLUMN IF NOT EXISTS lobby_remind_on_fill BOOLEAN DEFAULT TRUE",
        ):
            try:
                await conn.execute(lobby_sql)
            except Exception as e:
                log.debug("init_db lobby column: %s", e)

        await _migrate_legacy_reminders(conn)

        # Table for global emoji sets
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS global_emoji_sets (
                set_id TEXT PRIMARY KEY,
                name TEXT,
                data TEXT
            )
        """)
