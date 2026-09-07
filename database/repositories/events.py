from typing import Optional, Any
import re
import time
from utils.extra_data import serialize_extra_data
from ..connection import get_pool, DEFAULT_TIMEZONE
from .reminders import (
    normalize_reminders_for_store,
    normalize_reminder_message_for_store,
    replace_event_reminders,
)

def normalize_rsvp_allowed_role_ids_value(raw: Any) -> str:
    """
    Comma-separated Discord role IDs (digits only per segment).
    Empty string = any member who can see the message may RSVP.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    seen = set()
    out = []
    for part in s.split(","):
        digits = re.sub(r"\D", "", part.strip())
        if digits and digits not in seen:
            seen.add(digits)
            out.append(digits)
    return ",".join(out)

def normalize_image_urls_for_store(raw_images: Any) -> Optional[str]:
    """Normalizes image URL input (str or list of str) into a comma-separated string for DB storage."""
    if not raw_images:
        return None
    if isinstance(raw_images, list):
        cleaned = [str(u).strip() for u in raw_images if str(u).strip()]
        return ",".join(cleaned) if cleaned else None
    s = str(raw_images).strip()
    return s if s else None

async def check_config_exists(guild_id: str, config_name: str) -> bool:
    """Returns True if a config_name already exists in active_events for this guild."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM active_events WHERE guild_id = $1 AND config_name = $2 LIMIT 1", 
        str(guild_id), config_name
    )
    return row is not None

async def create_active_event(
    guild_id: str, 
    event_id: str, 
    config_name: str, 
    channel_id: int | str, 
    start_time: Optional[float | int], 
    data: Optional[dict[str, Any]] = None
) -> str:
    """Creates a new active event record in the database and configures its reminders."""
    if data is None:
        data = {}
    
    title = data.get("title")
    description = data.get("description")
    image_urls = normalize_image_urls_for_store(data.get("image_urls"))

    color = str(data.get("color") or "0x40C4FF")
    max_acc = int(data.get("max_accepted") or 0)
    
    ping_role_raw = str(data.get("ping_role") or "")
    ping_digits = re.sub(r"\D", "", ping_role_raw)
    ping_role = int(ping_digits) if ping_digits else 0
    
    end_time = data.get("end_time")
    recurrence = data.get("recurrence_type", "none")
    repost_trigger = data.get("repost_trigger", "before_start")
    repost_offset = data.get("repost_offset", "1h")
    timezone = data.get("timezone", DEFAULT_TIMEZONE)
    creator_id = str(data.get("creator_id") or "System")
    
    reminder_type = data.get("reminder_type", "none")
    rems = normalize_reminders_for_store(data)
    reminder_offset = rems[0]["offset_str"] if rems else str(data.get("reminder_offset", ""))
    reminder_sent = int(data.get("reminder_sent") or 0)
    reminder_message = normalize_reminder_message_for_store(data)

    recurrence_limit = int(data.get("recurrence_limit") or 0)
    recurrence_count = int(data.get("recurrence_count") or 0)
    icon_set = str(data.get("icon_set") or "standard")
    extra_data = serialize_extra_data(data.get("extra_data")) if data.get("extra_data") is not None else None

    temp_role_id = int(data.get("temp_role_id") or 0)
    use_temp_role = bool(data.get("use_temp_role", False))
    rsvp_allowed_role_ids = normalize_rsvp_allowed_role_ids_value(data.get("rsvp_allowed_role_ids"))
    lobby_mode = bool(data.get("lobby_mode", False))
    lobby_expires_at = data.get("lobby_expires_at")
    lobby_remind_on_fill = bool(data.get("lobby_remind_on_fill", True))

    pool = await get_pool()
    await pool.execute("""
        INSERT INTO active_events (
            event_id, config_name, channel_id, start_time,
            title, description, image_urls, color, max_accepted,
            ping_role, end_time, recurrence_type, repost_trigger,
            repost_offset, timezone, creator_id,
            reminder_type, reminder_offset, reminder_sent, reminder_message,
            recurrence_limit, recurrence_count, icon_set, extra_data,
            guild_id, temp_role_id, use_temp_role, rsvp_allowed_role_ids,
            lobby_mode, lobby_expires_at, lobby_remind_on_fill
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31
        )
    """,
        event_id, config_name, int(channel_id), start_time,
        title, description, image_urls, color, max_acc,
        ping_role, end_time, recurrence, repost_trigger,
        repost_offset, timezone, creator_id,
        reminder_type, reminder_offset, reminder_sent, reminder_message,
        recurrence_limit, recurrence_count, icon_set, extra_data,
        str(guild_id), temp_role_id, use_temp_role, rsvp_allowed_role_ids,
        lobby_mode, lobby_expires_at, lobby_remind_on_fill,
    )
    await replace_event_reminders(event_id, normalize_reminders_for_store(data))
    return event_id

async def get_active_events(guild_id: Optional[str] = None, include_all: bool = False) -> list[Any]:
    """Fetches active events, optionally filtered by guild_id and active status."""
    pool = await get_pool()
    if guild_id:
        if include_all:
            return await pool.fetch("SELECT * FROM active_events WHERE guild_id = $1", str(guild_id))
        return await pool.fetch("SELECT * FROM active_events WHERE guild_id = $1 AND status IN ('active', 'rescheduled')", str(guild_id))
    
    if include_all:
        return await pool.fetch("SELECT * FROM active_events")
    return await pool.fetch("SELECT * FROM active_events WHERE status IN ('active', 'rescheduled')")

async def get_active_events_by_config(config_name: str, guild_id: str) -> list[Any]:
    """Fetch all active events belonging to a specific series/configuration."""
    pool = await get_pool()
    return await pool.fetch("SELECT * FROM active_events WHERE config_name = $1 AND guild_id = $2", config_name, str(guild_id))

async def get_active_event(event_id: str, guild_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Fetch a single event by event_id."""
    pool = await get_pool()
    if guild_id:
        row = await pool.fetchrow("SELECT * FROM active_events WHERE event_id = $1 AND guild_id = $2", event_id, str(guild_id))
    else:
        row = await pool.fetchrow("SELECT * FROM active_events WHERE event_id = $1", event_id)
    return dict(row) if row else None

async def update_active_event(event_id: str, data: dict[str, Any]) -> None:
    """Updates active event record fields and refreshes reminder slots."""
    title = data.get("title")
    description = data.get("description")
    image_urls = normalize_image_urls_for_store(data.get("image_urls"))

    color = str(data.get("color") or "0x40C4FF")
    max_acc = int(data.get("max_accepted") or 0)
    
    ping_role_raw = str(data.get("ping_role") or "")
    ping_digits = re.sub(r"\D", "", ping_role_raw)
    ping_role = int(ping_digits) if ping_digits else 0
    
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    status = data.get("status", "active")
    recurrence = data.get("recurrence_type", "none")
    repost_trigger = data.get("repost_trigger", "before_start")
    repost_offset = data.get("repost_offset", "1h")
    timezone = data.get("timezone", DEFAULT_TIMEZONE)
    creator_id = str(data.get("creator_id") or "System")
    
    reminder_type = data.get("reminder_type", "none")
    rems = normalize_reminders_for_store(data)
    reminder_offset = rems[0]["offset_str"] if rems else str(data.get("reminder_offset", ""))
    reminder_sent = int(data.get("reminder_sent") or 0)

    recurrence_limit = int(data.get("recurrence_limit") or 0)
    recurrence_count = int(data.get("recurrence_count") or 0)
    icon_set = str(data.get("icon_set") or "standard")
    extra_data = serialize_extra_data(data.get("extra_data")) if data.get("extra_data") is not None else None

    temp_role_id = int(data.get("temp_role_id") or 0)
    use_temp_role = bool(data.get("use_temp_role", False))

    pool = await get_pool()
    need_row = (
        "reminder_message" not in data
        or "rsvp_allowed_role_ids" not in data
        or "lobby_mode" not in data
        or "lobby_expires_at" not in data
        or "lobby_remind_on_fill" not in data
    )
    row_m = None
    if need_row:
        row_m = await pool.fetchrow(
            """
            SELECT reminder_message, rsvp_allowed_role_ids,
                   lobby_mode, lobby_expires_at, lobby_remind_on_fill
            FROM active_events WHERE event_id = $1
            """,
            event_id,
        )

    if "reminder_message" in data:
        reminder_message = normalize_reminder_message_for_store(data)
    else:
        reminder_message = row_m["reminder_message"] if row_m else None

    if "rsvp_allowed_role_ids" in data:
        rsvp_allowed_role_ids = normalize_rsvp_allowed_role_ids_value(data.get("rsvp_allowed_role_ids"))
    else:
        raw_r = row_m["rsvp_allowed_role_ids"] if row_m else ""
        rsvp_allowed_role_ids = normalize_rsvp_allowed_role_ids_value(raw_r)

    if "lobby_mode" in data:
        lobby_mode = bool(data.get("lobby_mode"))
    else:
        lobby_mode = bool(row_m["lobby_mode"]) if row_m and row_m["lobby_mode"] is not None else False

    if "lobby_expires_at" in data:
        lobby_expires_at = data.get("lobby_expires_at")
    else:
        lobby_expires_at = row_m["lobby_expires_at"] if row_m else None

    if "lobby_remind_on_fill" in data:
        lobby_remind_on_fill = bool(data.get("lobby_remind_on_fill", True))
    else:
        v = row_m["lobby_remind_on_fill"] if row_m else None
        lobby_remind_on_fill = bool(v) if v is not None else True

    await pool.execute(
        """
        UPDATE active_events SET
            title = $1, description = $2, image_urls = $3,
            color = $4, max_accepted = $5, ping_role = $6,
            start_time = $7, end_time = $8, status = $9, recurrence_type = $10,
            repost_trigger = $11, repost_offset = $12, timezone = $13,
            creator_id = $14, reminder_type = $15, reminder_offset = $16,
            reminder_sent = $17, reminder_message = $18, recurrence_limit = $19, recurrence_count = $20,
            icon_set = $21, extra_data = $22,
            temp_role_id = $23, use_temp_role = $24, rsvp_allowed_role_ids = $25,
            lobby_mode = $26, lobby_expires_at = $27, lobby_remind_on_fill = $28
        WHERE event_id = $29
        """,
        title,
        description,
        image_urls,
        color,
        max_acc,
        ping_role,
        start_time,
        end_time,
        status,
        recurrence,
        repost_trigger,
        repost_offset,
        timezone,
        creator_id,
        reminder_type,
        reminder_offset,
        reminder_sent,
        reminder_message,
        recurrence_limit,
        recurrence_count,
        icon_set,
        extra_data,
        temp_role_id,
        use_temp_role,
        rsvp_allowed_role_ids,
        lobby_mode,
        lobby_expires_at,
        lobby_remind_on_fill,
        event_id,
    )

    if any(
        k in data
        for k in ("reminder_offsets", "reminder_offset", "reminder_type", "reminder_message", "reminder_messages")
    ):
        await replace_event_reminders(event_id, normalize_reminders_for_store(data))

async def update_event_status(event_id: str, status: str) -> None:
    """Simplified status update for cancellation, completion, or postponement."""
    pool = await get_pool()
    await pool.execute("UPDATE active_events SET status = $1 WHERE event_id = $2", status, event_id)

async def update_event_status_bulk(event_ids: list[str], status: str) -> None:
    """Update status for multiple events at once."""
    pool = await get_pool()
    await pool.execute("UPDATE active_events SET status = $1 WHERE event_id = ANY($2)", status, event_ids)

async def update_event_time(event_id: str, start_time: float | int) -> None:
    """Set a new start time for an event (postpone). Resets reminders."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE active_events SET start_time = $1, reminder_sent = 0 WHERE event_id = $2",
        start_time,
        event_id,
    )
    await pool.execute(
        "UPDATE event_reminders SET sent = 0 WHERE event_id = $1",
        event_id,
    )

async def set_lobby_start_time(event_id: str, start_ts: Optional[float | int]) -> None:
    """Lobby: set start_time when filled or NULL to reopen."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE active_events SET start_time = $1 WHERE event_id = $2",
        start_ts,
        event_id,
    )
    await pool.execute(
        "UPDATE event_reminders SET sent = 0 WHERE event_id = $1",
        event_id,
    )

async def update_active_events_metadata_bulk(event_ids: list[str], data: dict[str, Any]) -> None:
    """Updates metadata (like extra_data) for multiple events during bulk edit."""
    pool = await get_pool()
    extra_json = serialize_extra_data(data.get("extra_data")) if data.get("extra_data") is not None else None
    rsvp_allowed_role_ids = normalize_rsvp_allowed_role_ids_value(data.get("rsvp_allowed_role_ids"))
    image_urls = normalize_image_urls_for_store(data.get("image_urls"))

    await pool.execute("""
        UPDATE active_events SET 
            title = $1, description = $2, image_urls = $3, 
            color = $4, max_accepted = $5, icon_set = $6, extra_data = $7,
            temp_role_id = $8, use_temp_role = $9, rsvp_allowed_role_ids = $10
        WHERE event_id = ANY($11)
    """, 
        data.get("title"), data.get("description"), image_urls,
        data.get("color"), data.get("max_accepted"), data.get("icon_set"), 
        extra_json, data.get("temp_role_id"), data.get("use_temp_role", False),
        rsvp_allowed_role_ids,
        event_ids
    )

async def set_event_message(event_id: str, message_id: int, guild_id: Optional[str] = None) -> None:
    """Stores the Discord message ID for an active event."""
    pool = await get_pool()
    if guild_id:
        await pool.execute("UPDATE active_events SET message_id = $1 WHERE event_id = $2 AND guild_id = $3", message_id, event_id, str(guild_id))
    else:
        await pool.execute("UPDATE active_events SET message_id = $1 WHERE event_id = $2", message_id, event_id)

async def delete_active_event(event_id: str, guild_id: Optional[str] = None) -> None:
    """Deletes an active event and all associated reminders and RSVPs atomically."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM event_reminders WHERE event_id = $1", event_id)
            await conn.execute("DELETE FROM rsvps WHERE event_id = $1", event_id)
            if guild_id:
                await conn.execute("DELETE FROM active_events WHERE event_id = $1 AND guild_id = $2", event_id, str(guild_id))
            else:
                await conn.execute("DELETE FROM active_events WHERE event_id = $1", event_id)

async def get_endable_events(guild_id: str) -> list[Any]:
    """Fetches active events that have already started (for autocomplete)."""
    pool = await get_pool()
    now = time.time()
    return await pool.fetch("""
        SELECT event_id, title, start_time, config_name
        FROM active_events
        WHERE guild_id = $1 AND status = 'active'
          AND (start_time <= $2 OR start_time IS NULL)
        ORDER BY start_time DESC
        LIMIT 25
    """, str(guild_id), now)

async def get_user_active_events(guild_id: str, user_id: int | str) -> list[Any]:
    """Fetches upcoming events where the user is either the organizer or a participant."""
    pool = await get_pool()
    now = time.time()
    return await pool.fetch("""
        SELECT DISTINCT e.event_id, e.title, e.start_time, e.channel_id, e.message_id, 
               e.creator_id, r.status as user_status
        FROM active_events e
        LEFT JOIN rsvps r ON e.event_id = r.event_id AND r.user_id = $2
        WHERE e.guild_id = $1 
          AND (e.creator_id = $2::text OR r.user_id IS NOT NULL)
          AND e.status = 'active'
          AND (e.start_time > $3 OR e.start_time IS NULL)
        ORDER BY e.start_time ASC NULLS LAST
    """, str(guild_id), int(user_id), now - 86400)

async def get_user_event_history(guild_id: str, user_id: int | str, limit: int = 20) -> list[Any]:
    """Fetches past events where the user was the organizer or a participant."""
    pool = await get_pool()
    return await pool.fetch("""
        SELECT DISTINCT e.event_id, e.title, e.start_time, e.channel_id, e.message_id, 
               e.creator_id, r.status as user_status, r.attendance
        FROM active_events e
        LEFT JOIN rsvps r ON e.event_id = r.event_id AND r.user_id = $2
        WHERE e.guild_id = $1 
          AND e.status IN ('closed', 'ended')
          AND (e.creator_id = $2::text OR (r.user_id IS NOT NULL))
        ORDER BY e.start_time DESC NULLS LAST
        LIMIT $3
    """, str(guild_id), int(user_id), limit)

async def get_guild_events_export(guild_id: str) -> list[Any]:
    """Fetches all events for a guild with aggregated stats for CSV export."""
    pool = await get_pool()
    return await pool.fetch("""
        SELECT 
            e.event_id, 
            e.title, 
            e.creator_id, 
            e.start_time, 
            e.status, 
            e.config_name,
            (SELECT COUNT(*) FROM rsvps r WHERE r.event_id = e.event_id) as total_rsvps,
            (SELECT COUNT(*) FROM rsvps r WHERE r.event_id = e.event_id AND r.attendance = 'no_show') as no_shows
        FROM active_events e
        WHERE e.guild_id = $1
        ORDER BY e.start_time DESC
    """, str(guild_id))
