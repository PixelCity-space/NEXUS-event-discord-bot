import time
from typing import Any, Optional
import discord
import database
from utils.logger import log
from utils.enums import EventStatus
from cogs.event_ui import DynamicEventView
from services.recurrence_service import should_auto_archive_event, is_lobby_expired

# In-memory TTL cache for guild auto-archive settings (reduces per-event DB queries)
_archive_hours_cache: dict[str, tuple[float, float]] = {}
ARCHIVE_HOURS_CACHE_TTL = 300.0  # 5 minutes

async def get_cached_auto_archive_hours(guild_id: Optional[str]) -> float:
    """Retrieves cached auto-archive hours for a guild with a 5-minute TTL."""
    if not guild_id:
        return 12.0
    now = time.time()
    cached = _archive_hours_cache.get(str(guild_id))
    if cached and now < cached[1]:
        return cached[0]

    archive_hours_str = await database.get_guild_setting(guild_id, "auto_archive_hours", default="12")
    try:
        val = float(archive_hours_str) if archive_hours_str else 12.0
    except Exception:
        val = 12.0

    _archive_hours_cache[str(guild_id)] = (val, now + ARCHIVE_HOURS_CACHE_TTL)
    return val

async def refresh_event_card(bot: discord.Client, db_event: dict[str, Any]) -> None:
    """Refreshes the Discord UI message card for an event."""
    eid = db_event["event_id"]
    mid = db_event.get("message_id")
    cid = db_event.get("channel_id")
    if not mid or not cid:
        return
    channel = bot.get_channel(int(cid))
    if not channel:
        try:
            channel = await bot.fetch_channel(int(cid))
        except Exception as e:
            log.debug("[Scheduler] fetch_channel %s: %s", cid, e)
            return
    try:
        msg = await channel.fetch_message(int(mid))
        view = DynamicEventView(bot, eid, None)
        await view.prepare()
        await msg.edit(view=view)
    except Exception as e:
        log.error(
            "[Scheduler] Could not refresh event card %s: %s", eid, e,
            guild_id=db_event.get("guild_id"),
        )

async def handle_event_completion(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Marks one-time events as 'closed' after they have finished based on guild settings."""
    gid = db_event.get("guild_id")
    archive_hours = await get_cached_auto_archive_hours(gid)

    if should_auto_archive_event(db_event, now, archive_hours=archive_hours):
        await database.update_event_status(db_event["event_id"], EventStatus.CLOSED)
        log.info(
            "[Lifecycle] Auto-archived expired event %s (Threshold: %sh)",
            db_event["event_id"], archive_hours, guild_id=gid
        )
        await refresh_event_card(bot, db_event)

async def handle_lobby_expiry(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Marks fill-to-start lobbies as 'lobby_expired' if their expiration timestamp has passed."""
    if is_lobby_expired(db_event, now):
        await database.update_event_status(db_event["event_id"], EventStatus.LOBBY_EXPIRED)
        await refresh_event_card(bot, db_event)
