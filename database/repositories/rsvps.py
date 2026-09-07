from typing import Optional, Any
import time
from ..connection import get_pool

async def get_rsvps(event_id: str) -> list[Any]:
    """Fetches all RSVP records for an event (user_id, status)."""
    pool = await get_pool()
    return await pool.fetch("SELECT user_id, status FROM rsvps WHERE event_id = $1", event_id)

async def update_rsvp(event_id: str, user_id: int, status: str) -> None:
    """Inserts or updates an RSVP status for a user, updating joined_at if the status changes."""
    now = time.time()
    pool = await get_pool()
    await pool.execute("""
        INSERT INTO rsvps (event_id, user_id, status, joined_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT(event_id, user_id) DO UPDATE SET 
            status = EXCLUDED.status,
            joined_at = CASE WHEN rsvps.status != EXCLUDED.status THEN EXCLUDED.joined_at ELSE rsvps.joined_at END
    """, event_id, user_id, status, now)

async def get_rsvps_with_time(event_id: str) -> list[Any]:
    """Fetches RSVPs ordered by join timestamp (FIFO queue)."""
    pool = await get_pool()
    return await pool.fetch(
        "SELECT user_id, status, joined_at FROM rsvps WHERE event_id = $1 ORDER BY joined_at ASC", 
        event_id
    )

async def promote_next_waiting(event_id: str, waiting_status: str, target_status: str) -> Optional[int]:
    """Promotes the earliest queued user from waiting status to target status."""
    pool = await get_pool()
    row = await pool.fetchrow("""
        SELECT user_id FROM rsvps 
        WHERE event_id = $1 AND status = $2 
        ORDER BY joined_at ASC LIMIT 1
    """, event_id, waiting_status)
    
    if row:
        user_id = int(dict(row)["user_id"])
        await pool.execute(
            "UPDATE rsvps SET status = $1 WHERE event_id = $2 AND user_id = $3", 
            target_status, event_id, user_id
        )
        return user_id
    return None

async def join_or_update_rsvp_atomic(
    event_id: str,
    user_id: int,
    status: str,
    positive_statuses: list[str],
    max_accepted: int = 0,
    role_limits: Optional[dict[str, int]] = None,
    use_waiting_list: bool = True,
    waiting_list_limit: int = 0,
) -> dict[str, Any]:
    """
    Atomically joins or updates an RSVP for a user under a PostgreSQL row-level lock.
    Guarantees strict concurrency protection against overbooking and race conditions.
    Returns:
        dict with keys:
            - target_status: Optional[str] (e.g. 'accepted', 'wait_accepted', 'declined', or None if full)
            - old_status: Optional[str]
            - is_full: bool
            - is_waitlist: bool
            - error: Optional[str] ('position_full', 'waitlist_full', None)
    """
    pool = await get_pool()
    role_limits = role_limits or {}
    now = time.time()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Lock active_events row to serialize concurrent RSVPs for this event
            await conn.execute(
                "SELECT event_id FROM active_events WHERE event_id = $1 FOR UPDATE",
                event_id,
            )

            # 2. Query all existing RSVPs under exclusive lock
            rows = await conn.fetch(
                "SELECT user_id, status, joined_at FROM rsvps WHERE event_id = $1 ORDER BY joined_at ASC FOR UPDATE",
                event_id,
            )
            rsvps = [dict(r) for r in rows]

            # 3. Locate user's existing status
            old_status = next((r["status"] for r in rsvps if int(r["user_id"]) == int(user_id)), None)

            # 4. Check capacity and limits if requesting a positive/limited status
            target_status = status
            is_target_positive = status in positive_statuses
            role_limit = role_limits.get(status)

            other_role_count = sum(1 for r in rsvps if r["status"] == status and int(r["user_id"]) != int(user_id))
            role_capped = role_limit is not None and other_role_count >= role_limit

            other_positive_count = sum(1 for r in rsvps if r["status"] in positive_statuses and int(r["user_id"]) != int(user_id))
            event_capped = is_target_positive and max_accepted > 0 and other_positive_count >= max_accepted

            if role_capped or event_capped:
                if use_waiting_list:
                    waitlist_target = f"wait_{status}"
                    if waiting_list_limit > 0:
                        other_waitlist_count = sum(
                            1 for r in rsvps
                            if str(r["status"]).startswith("wait_") and int(r["user_id"]) != int(user_id)
                        )
                        if other_waitlist_count >= waiting_list_limit and not str(old_status).startswith("wait_"):
                            return {
                                "target_status": None,
                                "old_status": old_status,
                                "is_full": True,
                                "is_waitlist": False,
                                "error": "waitlist_full",
                            }
                    target_status = waitlist_target
                else:
                    return {
                        "target_status": None,
                        "old_status": old_status,
                        "is_full": True,
                        "is_waitlist": False,
                        "error": "position_full",
                    }

            # 5. Upsert RSVP record in the database
            await conn.execute("""
                INSERT INTO rsvps (event_id, user_id, status, joined_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(event_id, user_id) DO UPDATE SET 
                    status = EXCLUDED.status,
                    joined_at = CASE WHEN rsvps.status != EXCLUDED.status THEN EXCLUDED.joined_at ELSE rsvps.joined_at END
            """, event_id, int(user_id), target_status, now)

            return {
                "target_status": target_status,
                "old_status": old_status,
                "is_full": False,
                "is_waitlist": str(target_status).startswith("wait_"),
                "error": None,
            }


async def promote_waiting_users_atomic(
    event_id: str,
    positive_statuses: list[str],
    max_accepted: int = 0,
    role_limits: Optional[dict[str, int]] = None,
) -> list[tuple[int, str]]:
    """
    Atomically evaluates and promotes eligible waiting list users under a PostgreSQL row-level lock.
    Guarantees no race condition or duplicate promotion occurs when slots are vacated concurrently.
    Returns: list of (promoted_user_id, target_status) tuples.
    """
    pool = await get_pool()
    role_limits = role_limits or {}
    promoted: list[tuple[int, str]] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Lock the active event row for exclusive evaluation during promotion
            await conn.execute(
                "SELECT event_id FROM active_events WHERE event_id = $1 FOR UPDATE",
                event_id,
            )

            # 2. Fetch fresh RSVPs within the locked transaction in FIFO order
            rows = await conn.fetch(
                "SELECT user_id, status, joined_at FROM rsvps WHERE event_id = $1 ORDER BY joined_at ASC FOR UPDATE",
                event_id,
            )
            rsvps = [dict(r) for r in rows]

            waiting = [r for r in rsvps if str(r["status"]).startswith("wait_")]
            if not waiting:
                return []

            for w in waiting:
                current_acc = sum(1 for r in rsvps if r["status"] in positive_statuses)
                if max_accepted > 0 and current_acc >= max_accepted:
                    break

                wait_status = str(w["status"])
                target_status = wait_status.replace("wait_", "")

                role_limit = role_limits.get(target_status)
                if role_limit and sum(1 for r in rsvps if r["status"] == target_status) >= role_limit:
                    continue

                user_id = int(w["user_id"])
                await conn.execute(
                    "UPDATE rsvps SET status = $1 WHERE event_id = $2 AND user_id = $3",
                    target_status,
                    event_id,
                    user_id,
                )

                for r in rsvps:
                    if r["user_id"] == user_id:
                        r["status"] = target_status
                        break

                promoted.append((user_id, target_status))

    return promoted

async def get_attendance_eligible_events(guild_id: str) -> list[Any]:
    """Fetches events from the last 7 days that have started."""
    pool = await get_pool()
    now = time.time()
    one_week_ago = now - (7 * 86400)
    return await pool.fetch("""
        SELECT event_id, title, start_time, status
        FROM active_events
        WHERE guild_id = $1 AND start_time < $2 AND start_time > $3
        ORDER BY start_time DESC
    """, str(guild_id), now, one_week_ago)

async def get_event_attendance_data(event_id: str) -> list[Any]:
    """Fetches RSVPs and their current attendance status."""
    pool = await get_pool()
    return await pool.fetch("""
        SELECT user_id, status, attendance
        FROM rsvps
        WHERE event_id = $1
        ORDER BY status, user_id
    """, event_id)

async def update_rsvp_attendance(event_id: str, user_id: int, status: str) -> None:
    """Updates the attendance column (present / no_show)."""
    pool = await get_pool()
    await pool.execute("""
        UPDATE rsvps
        SET attendance = $1
        WHERE event_id = $2 AND user_id = $3
    """, status, event_id, int(user_id))

async def get_guild_reliability_stats(guild_id: str, all_time: bool = False) -> list[Any]:
    """Fetches user reliability and no-show stats for a guild."""
    pool = await get_pool()
    now = time.time()
    
    where_clause = "WHERE e.guild_id = $1"
    params: list[Any] = [str(guild_id)]
    
    if not all_time:
        where_clause += " AND e.start_time <= $2"
        params.append(now)
        
    query = f"""
        SELECT 
            r.user_id, 
            COUNT(*) as total_past_rsvps,
            SUM(CASE WHEN r.attendance = 'no_show' THEN 1 ELSE 0 END) as noshow_count
        FROM rsvps r
        JOIN active_events e ON r.event_id = e.event_id
        {where_clause}
        GROUP BY r.user_id
        HAVING SUM(CASE WHEN r.attendance = 'no_show' THEN 1 ELSE 0 END) > 0
        ORDER BY noshow_count DESC
    """
    return await pool.fetch(query, *params)

async def get_event_reliability_audit(event_id: str, guild_id: str) -> list[Any]:
    """Fetches reliability stats for all participants of a specific event."""
    pool = await get_pool()
    now = time.time()
    return await pool.fetch("""
        WITH participants AS (
            SELECT DISTINCT user_id FROM rsvps WHERE event_id = $1
        )
        SELECT 
            p.user_id, 
            COUNT(r2.event_id) as total_past_rsvps,
            SUM(CASE WHEN r2.attendance = 'no_show' THEN 1 ELSE 0 END) as noshow_count
        FROM participants p
        LEFT JOIN rsvps r2 ON p.user_id = r2.user_id
        LEFT JOIN active_events e ON r2.event_id = e.event_id AND e.guild_id = $2 AND e.start_time < $3
        GROUP BY p.user_id
        ORDER BY noshow_count DESC
    """, event_id, str(guild_id), now)

async def get_guild_rsvps_export(guild_id: str) -> list[Any]:
    """Fetches all RSVP records for a guild joined with event titles."""
    pool = await get_pool()
    return await pool.fetch("""
        SELECT 
            e.title as event_title, 
            r.user_id, 
            r.status, 
            r.joined_at, 
            r.attendance
        FROM rsvps r
        JOIN active_events e ON r.event_id = e.event_id
        WHERE e.guild_id = $1
        ORDER BY e.start_time DESC, r.joined_at DESC
    """, str(guild_id))
