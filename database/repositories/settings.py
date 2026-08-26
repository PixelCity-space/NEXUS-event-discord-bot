from typing import Optional, Any
from ..connection import get_pool
from utils.logger import log

async def save_guild_setting(guild_id: int | str, key: str, value: str) -> None:
    """Upsert a guild setting with robust logging and PK enforcement."""
    pool = await get_pool()
    log.info(f"DB: Saving guild setting - GID: {guild_id} ({type(guild_id)}), Key: {key}, Val: {value}")
    try:
        await pool.execute('''
            INSERT INTO guild_settings (guild_id, key, value) 
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value
        ''', str(guild_id), key, str(value))
        log.info(f"DB: Successfully saved {key}")
    except Exception as e:
        log.error(f"DB ERROR saving guild setting {key}: {e}")
        raise e

async def get_guild_setting(guild_id: int | str, key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a specific guild setting."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT value FROM guild_settings WHERE guild_id = $1 AND key = $2", str(guild_id), key)
    log.info(f"DB: Get guild setting - GID: {guild_id}, Key: {key}, Found: {row is not None}")
    if row:
        return str(row['value'])
    return default

async def get_all_guild_settings(guild_id: int | str) -> dict[str, str]:
    """Get all settings for a guild."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT key, value FROM guild_settings WHERE guild_id = $1", str(guild_id))
    return {str(r['key']): str(r['value']) for r in rows}

async def save_global_setting(key: str, value: str) -> None:
    """Upsert a global bot setting."""
    pool = await get_pool()
    await pool.execute('''
        INSERT INTO global_settings (key, value) 
        VALUES ($1, $2)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    ''', key, str(value))

async def get_global_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a specific global setting."""
    pool = await get_pool()
    row = await pool.fetchrow("SELECT value FROM global_settings WHERE key = $1", key)
    if row:
        return str(row['value'])
    return default

async def save_guild_translation(guild_id: int | str, key: str, value: str) -> None:
    """Save a per-guild translation override."""
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO guild_translations (guild_id, key, value)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value
    """, str(guild_id), key, value)

async def get_guild_translations(guild_id: int | str) -> dict[str, str]:
    """Fetch all translation string overrides for a guild."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT key, value FROM guild_translations WHERE guild_id = $1", str(guild_id))
    return {str(r["key"]): str(r["value"]) for r in rows}

async def delete_guild_translation(guild_id: int | str, key: str) -> None:
    """Delete a per-guild translation override."""
    pool = await get_pool()
    await pool.execute("DELETE FROM guild_translations WHERE guild_id = $1 AND key = $2", str(guild_id), key)

async def reset_guild_data(guild_id: int | str) -> None:
    """Remove all bot-owned data for a guild (events, RSVPs, drafts, emojis, settings, translations)."""
    pool = await get_pool()
    gid = str(guild_id)
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM event_reminders WHERE event_id IN (SELECT event_id FROM active_events WHERE guild_id = $1)",
            gid,
        )
        await conn.execute(
            "DELETE FROM rsvps WHERE event_id IN (SELECT event_id FROM active_events WHERE guild_id = $1)",
            gid,
        )
        await conn.execute("DELETE FROM active_events WHERE guild_id = $1", gid)
        await conn.execute("DELETE FROM event_drafts WHERE guild_id = $1", gid)
        await conn.execute("DELETE FROM guild_emoji_sets WHERE guild_id = $1", gid)
        await conn.execute("DELETE FROM guild_settings WHERE guild_id = $1", gid)
        await conn.execute("DELETE FROM guild_translations WHERE guild_id = $1", gid)

async def get_global_stats() -> dict[str, int]:
    """Returns bot-wide statistics for the Master Hub."""
    pool = await get_pool()
    guild_count = await pool.fetchval("SELECT COUNT(DISTINCT guild_id) FROM guild_settings")
    event_count = await pool.fetchval("SELECT COUNT(*) FROM active_events")
    rsvp_count = await pool.fetchval("SELECT COUNT(*) FROM rsvps")
    
    return {
        "guilds": int(guild_count or 0),
        "events": int(event_count or 0),
        "rsvps": int(rsvp_count or 0)
    }
