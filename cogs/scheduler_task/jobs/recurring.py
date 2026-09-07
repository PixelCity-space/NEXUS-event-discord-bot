from typing import Any
import uuid
import datetime
import discord
import database
from utils.emojis import PING
from utils.i18n import t, load_guild_translations
from utils.logger import log
from utils.enums import EventStatus
from utils.templates import get_event_conf
from utils.extra_data import parse_extra_data
from cogs.event_ui import DynamicEventView
from services.recurrence_service import evaluate_repost_readiness

async def handle_reposting(bot: discord.Client, db_event: dict[str, Any], now: float) -> None:
    """Checks if a recurring event needs to be reposted and spawns the next occurrence."""
    config_name = db_event.get("config_name")
    if not config_name:
        return

    event_conf = get_event_conf(config_name) or {}
    old_event_id = db_event["event_id"]

    is_ready, next_start, terminal_status = evaluate_repost_readiness(db_event, event_conf, now)

    if terminal_status:
        await database.update_event_status(old_event_id, terminal_status)
        log.info(
            "[Scheduler] Recurring series for %s set to terminal status '%s'.",
            old_event_id, terminal_status,
            guild_id=db_event.get("guild_id"),
        )
        return

    if not is_ready or next_start is None:
        return

    # Mark previous event instance as closed
    await database.update_event_status(old_event_id, EventStatus.CLOSED)

    # Spawn new instance
    new_event_id = str(uuid.uuid4())[:8]
    channel_id = event_conf.get("channel_id") or db_event["channel_id"]

    rec_count = int(db_event.get("recurrence_count") or 0)
    rec_limit = int(db_event.get("recurrence_limit") or 0)

    active_conf = dict(event_conf)
    active_conf.update(dict(db_event))
    active_conf["recurrence_count"] = rec_count + 1
    active_conf["recurrence_limit"] = rec_limit

    await database.create_active_event(
        guild_id=db_event.get("guild_id"),
        event_id=new_event_id,
        config_name=config_name,
        channel_id=channel_id,
        start_time=next_start,
        data=active_conf
    )

    guild_id = db_event.get("guild_id")
    if guild_id:
        await load_guild_translations(guild_id)

    cid = int(channel_id)
    channel = bot.get_channel(cid)
    if not channel:
        try:
            channel = await bot.fetch_channel(cid)
        except Exception as e:
            log.error(
                "[Scheduler] Failed to fetch channel %s for reposted event %s: %s",
                cid, new_event_id, e,
                guild_id=guild_id,
            )
            return

    try:
        view = DynamicEventView(bot, new_event_id, event_conf)
        await view.prepare()

        ping_role = active_conf.get("ping_role") or active_conf.get("ping_role_id")
        ping_prefix = ""
        if ping_role and str(ping_role).isdigit() and int(ping_role) > 0:
            ping_prefix = f"{PING} <@&{ping_role}> "

        content = f"{ping_prefix}{t('MSG_REC_ALERT', guild_id=guild_id)}".strip()
        if content:
            await channel.send(content=content)
        new_msg = await channel.send(view=view)
        await database.set_event_message(new_event_id, new_msg.id)
        bot.add_view(view)

        if event_conf.get("use_threads"):
            try:
                title = event_conf.get("title") or "Event"
                thread_name = title
                
                if next_start and not event_conf.get("lobby_mode"):
                    dt = datetime.datetime.fromtimestamp(float(next_start))
                    thread_name = f"{title} - {dt.strftime('%m/%d')}"
                
                thread = await new_msg.create_thread(name=thread_name[:100])
                
                extra_dto = parse_extra_data(event_conf.get("extra_data"))
                extra_dto.thread_id = thread.id
                event_conf["extra_data"] = extra_dto.to_json()
                await database.update_active_event(new_event_id, event_conf)
                
                log.info("[Scheduler] Created thread '%s' for reposted event %s", thread_name, new_event_id, guild_id=guild_id)
            except Exception as te:
                log.error("[Scheduler] Failed to create thread for reposted event: %s", te, guild_id=guild_id)
    except Exception as e:
        log.error(
            "[Scheduler] Failed to send reposted event card %s to channel %s: %s",
            new_event_id, cid, e,
            guild_id=guild_id,
        )
