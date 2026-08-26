from typing import Optional, Any
from ..connection import get_pool, MAX_EVENT_REMINDERS

def normalize_reminders_for_store(data: dict) -> list[dict[str, Any]]:
    """Parses offsets and messages into a list of dict objects for DB storage."""
    if data.get("lobby_mode"):
        return []
        
    raw_offsets = data.get("reminder_offsets") or []
    if not isinstance(raw_offsets, list):
        one = str(data.get("reminder_offset") or "").strip()
        raw_offsets = [one] if one else []
        
    raw_msgs = data.get("reminder_messages") or []
    if not isinstance(raw_msgs, list):
        raw_msgs = []

    out = []
    for idx, full_offset in enumerate(raw_offsets[:MAX_EVENT_REMINDERS]):
        parts = [p.strip() for p in str(full_offset).split(",")]
        off_str = parts[0]
        
        # Defaults
        method = "ping"
        target = "coming"
        
        if len(parts) == 2:
            p2 = parts[1].lower()
            if p2 in ("dm", "ping", "both", "none"):
                method = p2
            else:
                target = parts[1]
        elif len(parts) >= 3:
            method = parts[1] or "ping"
            target = parts[2] or "coming"
        
        cmsg = raw_msgs[idx] if idx < len(raw_msgs) else None
        if cmsg:
            cmsg = str(cmsg).strip() or None
            
        out.append({
            "offset_str": off_str,
            "method": method,
            "target": target,
            "custom_message": cmsg
        })
    return out

def normalize_reminder_message_for_store(data: dict) -> Optional[str]:
    """Optional shared reminder message body."""
    m = data.get("reminder_message")
    if m is None:
        return None
    s = str(m).strip()
    return s if s else None

async def get_event_reminders(event_id: str) -> list[Any]:
    """Fetches all reminder slots configured for an event ordered by slot index."""
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT slot_idx, offset_str, method, target, custom_message, sent
        FROM event_reminders
        WHERE event_id = $1
        ORDER BY slot_idx ASC
        """,
        event_id,
    )

async def replace_event_reminders(event_id: str, reminders: list[dict[str, Any]]) -> None:
    """Replaces reminder slots for an event while preserving 'sent' status if offset has not changed."""
    rems = reminders[:MAX_EVENT_REMINDERS]
    pool = await get_pool()
    old_rows = await get_event_reminders(event_id)
    old = {r["slot_idx"]: (r["offset_str"], int(r["sent"] or 0)) for r in old_rows}
    
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM event_reminders WHERE event_id = $1", event_id)
        for idx, r in enumerate(rems):
            off = r.get("offset_str", "")
            method = r.get("method", "ping")
            target = r.get("target", "coming")
            msg = r.get("custom_message")
            
            prev = old.get(idx)
            sent = 1 if prev and prev[0] == off and prev[1] == 1 else 0
            
            await conn.execute(
                """
                INSERT INTO event_reminders (event_id, slot_idx, offset_str, method, target, custom_message, sent)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                event_id,
                idx,
                off,
                method,
                target,
                msg,
                sent,
            )
            
    if not rems:
        await pool.execute(
            "UPDATE active_events SET reminder_sent = 0 WHERE event_id = $1", event_id
        )
        return
        
    pending = await pool.fetchval(
        "SELECT COUNT(*) FROM event_reminders WHERE event_id = $1 AND sent = 0",
        event_id,
    )
    await pool.execute(
        "UPDATE active_events SET reminder_sent = $1 WHERE event_id = $2",
        1 if pending == 0 else 0,
        event_id,
    )

async def mark_reminder_slot_sent(event_id: str, slot_idx: int) -> None:
    """Marks a specific reminder slot as sent, updating active_events if all are sent."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE event_reminders SET sent = 1 WHERE event_id = $1 AND slot_idx = $2",
        event_id,
        slot_idx,
    )
    pending = await pool.fetchval(
        "SELECT COUNT(*) FROM event_reminders WHERE event_id = $1 AND sent = 0",
        event_id,
    )
    if pending == 0:
        await pool.execute(
            "UPDATE active_events SET reminder_sent = 1 WHERE event_id = $1", event_id
        )

async def mark_all_reminder_slots_sent(event_id: str) -> None:
    """Marks all reminder slots as sent for an event."""
    pool = await get_pool()
    await pool.execute("UPDATE event_reminders SET sent = 1 WHERE event_id = $1", event_id)
    await pool.execute(
        "UPDATE active_events SET reminder_sent = 1 WHERE event_id = $1", event_id
    )

async def mark_reminder_sent(event_id: str, guild_id: Optional[int | str] = None) -> None:
    """Legacy reminder sent flag update on active_events."""
    pool = await get_pool()
    if guild_id:
        await pool.execute("UPDATE active_events SET reminder_sent = 1 WHERE event_id = $1 AND guild_id = $2", event_id, str(guild_id))
    else:
        await pool.execute("UPDATE active_events SET reminder_sent = 1 WHERE event_id = $1", event_id)
