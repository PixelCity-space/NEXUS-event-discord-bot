from typing import Optional, Any
import json
import time
from ..connection import get_pool

async def save_draft(
    guild_id: str, 
    draft_id: str, 
    creator_id: str, 
    title: str, 
    data: dict[str, Any]
) -> None:
    """Upserts an event draft with JSON data."""
    data_json = json.dumps(data)
    now = time.time()
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO event_drafts (draft_id, creator_id, title, data, updated_at, guild_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (draft_id) DO UPDATE SET
            creator_id = EXCLUDED.creator_id,
            title = EXCLUDED.title,
            data = EXCLUDED.data,
            updated_at = EXCLUDED.updated_at
    """, draft_id, str(creator_id), title, data_json, now, str(guild_id))

async def get_draft(draft_id: str, guild_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Fetches a specific event draft."""
    pool = await get_pool()
    if guild_id:
        row = await pool.fetchrow("SELECT * FROM event_drafts WHERE draft_id = $1 AND guild_id = $2", draft_id, str(guild_id))
    else:
        row = await pool.fetchrow("SELECT * FROM event_drafts WHERE draft_id = $1", draft_id)
    return dict(row) if row else None

async def delete_draft(draft_id: str, guild_id: Optional[str] = None) -> None:
    """Deletes an event draft."""
    pool = await get_pool()
    if guild_id:
        await pool.execute("DELETE FROM event_drafts WHERE draft_id = $1 AND guild_id = $2", draft_id, str(guild_id))
    else:
        await pool.execute("DELETE FROM event_drafts WHERE draft_id = $1", draft_id)

async def get_user_drafts(guild_id: str, user_id: str) -> list[Any]:
    """Fetches all drafts for a user in a guild."""
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT draft_id, title, updated_at
        FROM event_drafts
        WHERE guild_id = $1 AND creator_id = $2
        ORDER BY updated_at DESC
        """,
        str(guild_id),
        str(user_id),
    )

async def delete_all_user_drafts(guild_id: str, user_id: str) -> None:
    """Removes every draft owned by the user in this guild."""
    pool = await get_pool()
    await pool.execute(
        "DELETE FROM event_drafts WHERE guild_id = $1 AND creator_id = $2",
        str(guild_id),
        str(user_id),
    )
