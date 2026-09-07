from typing import Any
import json
from ..connection import get_pool

async def save_emoji_set(
    guild_id: str, 
    set_id: str, 
    name: str, 
    data: dict[str, Any] | list[Any]
) -> None:
    """Upserts a guild-specific emoji set."""
    data_json = json.dumps(data)
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO guild_emoji_sets (guild_id, set_id, name, data)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (guild_id, set_id) DO UPDATE SET
            name = EXCLUDED.name,
            data = EXCLUDED.data
    """, str(guild_id), set_id, name, data_json)

async def get_emoji_sets(guild_id: str) -> list[Any]:
    """Fetches all emoji sets for a specific guild."""
    pool = await get_pool()
    return await pool.fetch("SELECT * FROM guild_emoji_sets WHERE guild_id = $1", str(guild_id))

async def get_all_custom_emoji_sets() -> list[Any]:
    """Fetch all guild-specific emoji sets across all guilds."""
    pool = await get_pool()
    return await pool.fetch("SELECT * FROM guild_emoji_sets")

async def delete_emoji_set(guild_id: str, set_id: str) -> None:
    """Deletes a guild-specific emoji set."""
    pool = await get_pool()
    await pool.execute("DELETE FROM guild_emoji_sets WHERE guild_id = $1 AND set_id = $2", str(guild_id), set_id)

async def save_global_emoji_set(set_id: str, name: str, data: Any) -> None:
    """Upsert a global emoji set."""
    if isinstance(data, (dict, list)):
        data_json = json.dumps(data)
    elif isinstance(data, str):
        try:
            json.loads(data)
            data_json = data
        except Exception:
            data_json = json.dumps(data)
    else:
        data_json = json.dumps(data)
    
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO global_emoji_sets (set_id, name, data)
        VALUES ($1, $2, $3)
        ON CONFLICT (set_id) DO UPDATE SET name = EXCLUDED.name, data = EXCLUDED.data
    """, set_id, name, data_json)

async def get_all_global_emoji_sets() -> list[Any]:
    """Get all global emoji sets."""
    pool = await get_pool()
    return await pool.fetch("SELECT set_id, name, data FROM global_emoji_sets")

async def delete_global_emoji_set(set_id: str) -> None:
    """Delete a global emoji set."""
    pool = await get_pool()
    await pool.execute("DELETE FROM global_emoji_sets WHERE set_id = $1", set_id)

async def clear_global_emoji_sets() -> None:
    """Delete all global emoji sets."""
    pool = await get_pool()
    await pool.execute("DELETE FROM global_emoji_sets")
