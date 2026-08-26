from typing import Any
import discord
import database
from utils.logger import log

async def check_role_cleanup(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Deletes temporary Discord roles once the event has finished or been cancelled/closed."""
    temp_role_id = db_event.get("temp_role_id")
    if not temp_role_id:
        return

    should_delete = False
    end_ts = db_event.get("end_time")
    start_ts = db_event.get("start_time")
    status = db_event.get("status") or "active"
    lobby_mode = bool(db_event.get("lobby_mode"))

    if status in ("closed", "cancelled", "deleted", "lobby_expired"):
        should_delete = True
    elif lobby_mode:
        if start_ts is None:
            should_delete = False
        elif end_ts and now > end_ts:
            should_delete = True
        elif not end_ts and start_ts is not None and now > (float(start_ts) + 14400):
            should_delete = True
    else:
        if start_ts is not None:
            if end_ts and now > end_ts:
                should_delete = True
            elif not end_ts and now > (float(start_ts) + 14400):
                should_delete = True

    if should_delete:
        guild = bot.get_guild(int(db_event["guild_id"]))
        if guild:
            if not guild.me.guild_permissions.manage_roles:
                log.warning(f"[Scheduler] Missing 'Manage Roles' permission to delete role {temp_role_id} in guild {guild.id}")
            else:
                try:
                    role = guild.get_role(int(temp_role_id))
                    if role:
                        await role.delete(reason=f"Event {db_event['event_id']} finished/closed.")
                        log.info(f"[Scheduler] Deleted temp role {temp_role_id} for event {db_event['event_id']}")
                except Exception as e:
                    log.error(f"[Scheduler] Failed to delete role {temp_role_id}: {e}")
        
        # Clear from DB to prevent re-attempts even if permission was missing
        pool = await database.get_pool()
        await pool.execute("UPDATE active_events SET temp_role_id = 0 WHERE event_id = $1", db_event["event_id"])
