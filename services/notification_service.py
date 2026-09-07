import asyncio
from typing import Any, Optional, Union
import discord
from utils.text_utils import slugify
from utils.lobby_utils import positive_status_ids
from utils.logger import log

def normalize_rsvps(rsvps: list[Any]) -> list[dict[str, Any]]:
    """Normalizes RSVP records from database rows/tuples to a uniform list of dicts."""
    normalized: list[dict[str, Any]] = []
    for r in rsvps:
        if isinstance(r, dict):
            normalized.append({"user_id": int(r["user_id"]), "status": str(r["status"])})
        elif hasattr(r, "keys"):
            # asyncpg Record or sqlite Row
            normalized.append({"user_id": int(r["user_id"]), "status": str(r["status"])})
        elif isinstance(r, (tuple, list)) and len(r) >= 2:
            normalized.append({"user_id": int(r[0]), "status": str(r[1])})
    return normalized

def resolve_target_recipients(
    bot: discord.Client,
    db_event: dict[str, Any],
    target_raw: str,
    rsvps: list[Any],
    active_set: dict[str, Any],
    guild: Optional[discord.Guild] = None,
) -> list[int]:
    """
    Resolves target audience user IDs based on event settings, icon set, and target criteria.
    Supports 'all', 'coming'/'positive'/'accepted', 'not_coming'/'negative'/'declined',
    individual option labels/slugs, or Discord server role names.
    """
    normalized_rsvps = normalize_rsvps(rsvps)
    participants = [r for r in normalized_rsvps if not str(r["status"]).startswith("wait_")]

    target_key = slugify(target_raw or "coming")

    pos_ids = set([s.lower() for s in positive_status_ids(active_set)])
    for opt in active_set.get("options", []):
        if opt.get("positive"):
            pos_ids.add(opt["id"].lower())
    pos_ids.add("accepted")

    label_to_id: dict[str, str] = {}
    for opt in active_set.get("options", []):
        oid = opt["id"].lower()
        label_to_id[oid] = oid
        if opt.get("label"):
            label_to_id[slugify(opt["label"])] = oid
        if opt.get("list_label"):
            label_to_id[slugify(opt["list_label"])] = oid

    is_coming_alias = target_key in ["coming", "positive", "accepted"]
    is_not_coming_alias = target_key in ["not_coming", "negative", "declined"]

    target_user_ids: list[int] = []

    if target_key == "all":
        target_user_ids = [p["user_id"] for p in participants]
    elif is_coming_alias:
        target_user_ids = [p["user_id"] for p in participants if p["status"].lower() in pos_ids]
    elif is_not_coming_alias:
        target_user_ids = [p["user_id"] for p in participants if p["status"].lower() not in pos_ids]
    elif target_key in label_to_id:
        resolved_id = label_to_id[target_key]
        target_user_ids = [p["user_id"] for p in participants if p["status"].lower() == resolved_id]
    elif target_key in [p["status"].lower() for p in participants]:
        target_user_ids = [p["user_id"] for p in participants if p["status"].lower() == target_key]
    else:
        # Fallback to server role name lookup
        guild_id = db_event.get("guild_id")
        resolved_guild = guild or (bot.get_guild(int(guild_id)) if guild_id else None)
        if resolved_guild:
            role = discord.utils.get(resolved_guild.roles, name=target_raw)
            if role:
                target_user_ids = [m.id for m in role.members]

    # Deduplicate preserving order
    seen: set[int] = set()
    deduped: list[int] = []
    for uid in target_user_ids:
        if uid not in seen:
            seen.add(uid)
            deduped.append(uid)

    return deduped

async def send_event_alert(
    bot: discord.Client,
    channel_id: Optional[Union[int, str]],
    target_user_ids: list[int],
    method: str = "ping",
    embed: Optional[discord.Embed] = None,
    content: Optional[str] = None,
    temp_role_id: Optional[Union[int, str]] = None,
    dm_embed: Optional[discord.Embed] = None,
    dm_content: Optional[str] = None,
    max_pings: int = 50,
    include_target_mentions: bool = True,
) -> dict[str, int]:
    """
    Dispatches unified event notifications to a Discord channel and/or individual DMs.
    Handles method normalization ('ping'/'chat'/'channel', 'dm', 'both', 'none'),
    temp-role mentions, rate limits, and DM error logging.
    """
    method = (method or "ping").lower().strip()
    if method in ("none", ""):
        return {"channel_sent": 0, "dms_sent": 0, "dms_failed": 0}

    send_channel = method in ("ping", "channel", "chat", "both")
    send_dm = method in ("dm", "both")

    stats = {"channel_sent": 0, "dms_sent": 0, "dms_failed": 0}

    # 1. Send channel notification
    if send_channel and channel_id:
        try:
            cid = int(channel_id)
            channel = bot.get_channel(cid)
            if not channel:
                channel = await bot.fetch_channel(cid)

            if channel:
                mention_str = ""
                if include_target_mentions and target_user_ids:
                    if temp_role_id and int(temp_role_id) > 0:
                        mention_str = f"<@&{int(temp_role_id)}>"
                    else:
                        mention_str = ", ".join(f"<@{uid}>" for uid in target_user_ids[:max_pings])

                full_content = None
                if content and mention_str:
                    full_content = f"{mention_str}\n{content}" if not content.startswith(mention_str) else content
                elif mention_str:
                    full_content = mention_str
                elif content:
                    full_content = content

                await channel.send(content=full_content, embed=embed)
                stats["channel_sent"] = 1
        except Exception as e:
            log.warning("[NotificationService] Failed to send channel alert to %s: %s", channel_id, e)

    # 2. Send DM notifications concurrently with controlled rate limiting
    if send_dm and target_user_ids:
        active_dm_embed = dm_embed or embed
        active_dm_content = dm_content or content
        dm_sem = asyncio.Semaphore(5)

        async def _send_single_dm(uid: int) -> bool:
            async with dm_sem:
                try:
                    user = bot.get_user(uid)
                    if not user:
                        user = await bot.fetch_user(uid)
                    if user:
                        await user.send(content=active_dm_content, embed=active_dm_embed)
                        return True
                except Exception as e:
                    log.debug("[NotificationService] Could not send DM to %s: %s", uid, e)
                return False

        results = await asyncio.gather(*[_send_single_dm(uid) for uid in target_user_ids], return_exceptions=True)
        for res in results:
            if res is True:
                stats["dms_sent"] += 1
            else:
                stats["dms_failed"] += 1

    return stats
