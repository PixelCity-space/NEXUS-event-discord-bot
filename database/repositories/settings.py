from typing import Optional
from ..connection import get_pool
from utils.logger import log
from utils.cache import guild_cache

def _invalidate_guild_cache(gid: str) -> None:
    """Evicts a guild's configuration from both MemoryTTLCache and in-memory GUILD_CACHE."""
    guild_cache.delete_sync(gid)
    try:
        from utils.i18n import GUILD_CACHE
        GUILD_CACHE.pop(gid, None)
    except Exception:
        pass

async def save_guild_setting(guild_id: str, key: str, value: str) -> None:
    """Upsert a guild setting with PK enforcement."""
    pool = await get_pool()
    gid = str(guild_id)
    log.debug(f"DB: Saving guild setting - GID: {gid}, Key: {key}")
    try:
        await pool.execute('''
            INSERT INTO guild_settings (guild_id, key, value) 
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value
        ''', gid, key, str(value))
        _invalidate_guild_cache(gid)
        log.debug(f"DB: Successfully saved {key}")
    except Exception as e:
        log.error(f"DB ERROR saving guild setting {key}: {e}")
        raise e

async def get_guild_setting(guild_id: str, key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a specific guild setting."""
    pool = await get_pool()
    gid = str(guild_id)
    row = await pool.fetchrow("SELECT value FROM guild_settings WHERE guild_id = $1 AND key = $2", gid, key)
    log.debug(f"DB: Get guild setting - GID: {gid}, Key: {key}, Found: {row is not None}")
    if row:
        return str(row['value'])
    return default

async def get_all_guild_settings(guild_id: str) -> dict[str, str]:
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

async def save_guild_translation(guild_id: str, key: str, value: str) -> None:
    """Save a per-guild translation override."""
    pool = await get_pool()
    gid = str(guild_id)
    await pool.execute("""
        INSERT INTO guild_translations (guild_id, key, value)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, key) DO UPDATE SET value = EXCLUDED.value
    """, gid, key, value)
    _invalidate_guild_cache(gid)

async def get_guild_translations(guild_id: str) -> dict[str, str]:
    """Fetch all translation string overrides for a guild."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT key, value FROM guild_translations WHERE guild_id = $1", str(guild_id))
    return {str(r["key"]): str(r["value"]) for r in rows}

async def delete_guild_translation(guild_id: str, key: str) -> None:
    """Delete a per-guild translation override."""
    pool = await get_pool()
    gid = str(guild_id)
    await pool.execute("DELETE FROM guild_translations WHERE guild_id = $1 AND key = $2", gid, key)
    _invalidate_guild_cache(gid)

async def reset_guild_data(guild_id: str) -> None:
    """Remove all bot-owned data for a guild (events, RSVPs, drafts, emojis, settings, translations)."""
    pool = await get_pool()
    gid = str(guild_id)
    _invalidate_guild_cache(gid)
    async with pool.acquire() as conn:
        async with conn.transaction():
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
