from typing import Any
import discord
import database
from utils.logger import log
from cogs.event_ui import DynamicEventView
from services.recurrence_service import should_auto_archive_event, is_lobby_expired

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
            f"[Scheduler] Could not refresh event card {eid}: {e}",
            guild_id=db_event.get("guild_id"),
        )

async def handle_event_completion(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Marks one-time events as 'closed' after they have finished based on guild settings."""
    gid = db_event.get("guild_id")
    archive_hours_str = await database.get_guild_setting(gid, "auto_archive_hours", default="12")
    try:
        archive_hours = float(archive_hours_str) if archive_hours_str else 12.0
    except Exception:
        archive_hours = 12.0

    if should_auto_archive_event(db_event, now, archive_hours=archive_hours):
        await database.set_event_status(db_event["event_id"], "closed")
        log.info(f"[Lifecycle] Auto-archived expired event {db_event['event_id']} (Threshold: {archive_hours}h)", guild_id=gid)
        await refresh_event_card(bot, db_event)

async def handle_lobby_expiry(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Marks fill-to-start lobbies as 'lobby_expired' if their expiration timestamp has passed."""
    if is_lobby_expired(db_event, now):
        await database.update_event_status(db_event["event_id"], "lobby_expired")
        await refresh_event_card(bot, db_event)
