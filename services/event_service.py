from typing import Any, Optional, Union
import discord
from discord import app_commands
from dateutil import parser, tz
import database
from database import DEFAULT_TIMEZONE
from utils.i18n import t
from utils.logger import log

async def resolve_target_events(
    event_id: str,
    guild_id: Optional[int] = None,
    occurrence: Optional[int] = None,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]], Optional[list[str]]]:
    """
    Resolves event records from an event_id or series:config_name specifier.
    Returns: (primary_event_dict, all_matched_events_list, bulk_ids_list_if_series_root)
    """
    matched_events: list[dict[str, Any]] = []
    primary_event: Optional[dict[str, Any]] = None
    bulk_ids: Optional[list[str]] = None

    if event_id.startswith("series:"):
        config_name = event_id.replace("series:", "")
        series_events = await database.get_active_events_by_config(config_name, guild_id)
        if series_events:
            matched_events = [dict(ev) for ev in series_events]
            if occurrence is not None and 1 <= occurrence <= len(matched_events):
                primary_event = matched_events[occurrence - 1]
            elif matched_events:
                primary_event = matched_events[0]
                bulk_ids = [ev["event_id"] for ev in matched_events]
    else:
        db_event = await database.get_active_event(event_id, guild_id)
        if not db_event:
            db_event = await database.get_active_event(event_id)
        if db_event:
            primary_event = dict(db_event)
            matched_events = [primary_event]

    return primary_event, matched_events, bulk_ids

async def search_events_autocomplete(
    guild_id: Optional[int],
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    Unified autocomplete search for active events and series for a guild.
    """
    active_events = await database.get_all_active_events(guild_id)
    series: dict[str, list[dict[str, Any]]] = {}
    single_events: list[dict[str, Any]] = []

    for ev in active_events:
        cfg = ev.get("config_name")
        if cfg and cfg != "manual":
            if cfg not in series:
                series[cfg] = []
            series[cfg].append(ev)
        else:
            single_events.append(ev)

    results: list[app_commands.Choice[str]] = []
    q = (current or "").lower()

    # 1. Match series
    for config_name, evs in series.items():
        title = evs[0].get("title", config_name)
        if q and q not in title.lower() and q not in config_name.lower():
            continue
        label = t("LBL_SERIES_AUTOCOMPLETE", guild_id=guild_id, title=title, count=len(evs))
        results.append(app_commands.Choice(name=label[:100], value=f"series:{config_name}"))

    # 2. Match single events
    for ev in single_events:
        title = ev.get("title") or t("LBL_UNNAMED_EVENT", guild_id=guild_id)
        eid = ev["event_id"]
        if q and q not in title.lower() and q not in eid.lower():
            continue
        label = t("LBL_EVENT_AUTOCOMPLETE", guild_id=guild_id, title=title, id=eid)
        results.append(app_commands.Choice(name=label[:100], value=eid))

    return results[:25]

async def remove_events_with_cleanup(
    bot: discord.Client,
    events: list[dict[str, Any]],
    guild: Optional[discord.Guild] = None,
    actor: Optional[Union[discord.User, discord.Member, str]] = None,
) -> list[str]:
    """
    Deactivates card buttons in Discord channels, deletes temporary roles,
    and removes event records from the database.
    Returns list of removed event IDs.
    """
    removed_ids: list[str] = []

    for ev in events:
        eid = ev["event_id"]
        guild_id = ev.get("guild_id")
        resolved_guild = guild or (bot.get_guild(int(guild_id)) if guild_id else None)

        # 1. Update Discord card to deleted state and disable buttons
        msg_id = ev.get("message_id")
        chan_id = ev.get("channel_id")
        if msg_id and chan_id:
            try:
                channel = bot.get_channel(int(chan_id))
                if not channel:
                    channel = await bot.fetch_channel(int(chan_id))
                if channel:
                    msg = await channel.fetch_message(int(msg_id))
                    if msg:
                        from cogs.event_ui import DynamicEventView
                        ev_conf = dict(ev)
                        ev_conf["status"] = "deleted"
                        view = DynamicEventView(bot, eid, ev_conf)
                        await view.prepare()
                        for child in view.children:
                            if isinstance(child, discord.ui.Container):
                                for row in child.children:
                                    if isinstance(row, discord.ui.ActionRow):
                                        for item in row.children:
                                            if isinstance(item, discord.ui.Button):
                                                item.disabled = True
                        await msg.edit(view=view)
            except Exception as e:
                log.warning(f"[EventService] Could not update card for {eid}: {e}")

        # 2. Temp role deletion
        temp_role_id = ev.get("temp_role_id")
        if temp_role_id and resolved_guild:
            if resolved_guild.me.guild_permissions.manage_roles:
                try:
                    role = resolved_guild.get_role(int(temp_role_id))
                    if role:
                        reason = f"Event {eid} removed by {actor}" if actor else f"Event {eid} removed"
                        await role.delete(reason=reason)
                        log.info(f"[EventService] Deleted temp role {temp_role_id} for event {eid}")
                except Exception as e:
                    log.error(f"[EventService] Failed to delete role {temp_role_id}: {e}")

        # 3. Database deletion
        await database.delete_active_event(eid, guild_id)
        removed_ids.append(eid)

    return removed_ids

async def update_event_time_parsed(event_id: str, new_time_str: str) -> float:
    """Parses a time string using the bot's default timezone and updates the database."""
    local_tz = tz.gettz(DEFAULT_TIMEZONE)
    dt = parser.parse(new_time_str).replace(tzinfo=local_tz)
    timestamp = dt.timestamp()
    await database.update_event_time(event_id, timestamp)
    return timestamp
