import asyncio
from typing import Any, Optional
import discord
from discord import app_commands
import database
from utils.lobby_utils import positive_status_ids
from utils.i18n import t
from utils.templates import get_active_set

async def get_eligible_attendance_participants(
    event_id: str,
    icon_set_id: str,
) -> list[dict[str, Any]]:
    """
    Fetches RSVPs for an event and filters down to participants who selected a positive RSVP status.
    """
    rsvps = await database.get_event_attendance_data(event_id)
    active_set = get_active_set(icon_set_id)
    pos_ids = set(positive_status_ids(active_set))

    # Also capture positive flagged options and canonical aliases
    for opt in active_set.get("options", []):
        if opt.get("positive"):
            pos_ids.add(opt["id"])
    pos_ids.add("accepted")

    eligible = [dict(r) for r in rsvps if r["status"] in pos_ids]
    return eligible

def calculate_attendance_stats(participants: list[dict[str, Any]]) -> tuple[int, int, float]:
    """
    Calculates attended count, no-show count, and attendance percentage rate.
    Returns: (attended_count, noshow_count, attendance_rate_pct)
    """
    total = len(participants)
    if total == 0:
        return 0, 0, 0.0

    no_shows = sum(1 for p in participants if p.get("attendance") == "no_show")
    attended = total - no_shows
    rate = (attended / total) * 100.0
    return attended, no_shows, rate

async def toggle_user_attendance(
    event_id: str,
    user_id: int,
    current_attendance: str,
) -> str:
    """
    Toggles a user's attendance state between 'present' and 'no_show' and updates the database.
    Returns the new attendance status.
    """
    new_att = "present" if current_attendance == "no_show" else "no_show"
    await database.update_rsvp_attendance(event_id, int(user_id), new_att)
    return new_att

async def resolve_member_names_batch(
    bot: discord.Client,
    guild_id: Optional[str],
    user_ids: list[str],
    name_cache: dict[str, str],
) -> dict[str, str]:
    """
    Resolves Discord member display names in parallel for uncached user IDs.
    """
    missing_ids = [str(uid) for uid in user_ids if str(uid) not in name_cache]
    if not missing_ids or not guild_id:
        return name_cache

    try:
        gid_int = int(guild_id)
    except (ValueError, TypeError):
        return name_cache

    guild = bot.get_guild(gid_int)
    if not guild:
        return name_cache

    fetch_sem = asyncio.Semaphore(3)

    async def fetch(uid: str):
        try:
            # Fast path: check local Discord.py guild member cache without holding semaphore
            mem = guild.get_member(int(uid))
            if mem:
                return uid, mem.display_name

            # Slow path: fetch from Discord REST API with rate-limiting semaphore
            async with fetch_sem:
                mem = await guild.fetch_member(int(uid))
                return uid, mem.display_name
        except Exception:
            return uid, t("LBL_USER_DEFAULT", guild_id=str(gid_int)).replace("{uid}", str(uid))

    results = await asyncio.gather(*(fetch(uid) for uid in missing_ids))
    for uid, name in results:
        name_cache[uid] = name

    return name_cache

async def search_attendance_events_autocomplete(
    guild_id: Optional[str],
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    Generates autocomplete suggestions for events eligible for attendance auditing.
    """
    if not guild_id:
        return []
    events = await database.get_attendance_eligible_events(str(guild_id))
    choices: list[app_commands.Choice[str]] = []
    q = (current or "").lower()

    for e in events:
        eid = e["event_id"]
        title = e.get("title", eid)
        label = f"{title} ({eid})"
        if q in label.lower() or q in eid.lower():
            choices.append(app_commands.Choice(name=label[:100], value=eid))

    return choices[:25]
