import asyncio
import json
import random
import time
from typing import Any
import discord
import database
from utils.logger import log
from utils.i18n import t

# In-memory TTL caches to eliminate redundant database polling every 15-30 seconds
_stats_cache: dict[str, Any] = {"data": {}, "expires_at": 0.0}
_config_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}

STATS_CACHE_TTL = 300.0   # 5 minutes
CONFIG_CACHE_TTL = 60.0   # 1 minute

async def _get_cached_stats() -> dict[str, int]:
    """Fetches global bot statistics with a 5-minute in-memory TTL cache."""
    now = time.time()
    if _stats_cache["expires_at"] > now and _stats_cache["data"]:
        return _stats_cache["data"]

    stats = await database.get_global_stats()
    _stats_cache["data"] = stats
    _stats_cache["expires_at"] = now + STATS_CACHE_TTL
    return stats

async def _get_cached_presence_config() -> dict[str, Any]:
    """Fetches and parses bot presence configuration with a 1-minute in-memory TTL cache."""
    now = time.time()
    if _config_cache["expires_at"] > now and _config_cache["data"] is not None:
        return _config_cache["data"]

    config = {
        "time": 30,
        "mode": "random",
        "statuses": [{"id": "default", "type": "watching", "text": t("PRESENCE_DEFAULT", guild_id=None)}]
    }

    db_presence = await database.get_global_setting("bot_presence_list")
    parsed = None
    if db_presence:
        try:
            parsed = json.loads(db_presence)
        except json.JSONDecodeError:
            log.warning("[Presence] bot_presence_list is not valid JSON; using defaults.")

    if isinstance(parsed, dict):
        config.update(parsed)
    elif isinstance(parsed, list):
        log.warning(
            "[Presence] bot_presence_list uses deprecated list JSON; "
            "store a dict {time, mode, statuses} via Master. Using defaults for this cycle."
        )

    _config_cache["data"] = config
    _config_cache["expires_at"] = now + CONFIG_CACHE_TTL
    return config

async def run_presence_rotator(bot: discord.Client):
    """Periodically updates the bot's rich presence from database settings or default configuration."""
    await bot.wait_until_ready()
    
    last_index = -1
    
    while not bot.is_closed():
        try:
            config = await _get_cached_presence_config()

            statuses = config.get("statuses", [])
            if not statuses:
                statuses = [{"id": "default", "type": "watching", "text": t("PRESENCE_DEFAULT", guild_id=None)}]

            # Select next status entry
            if config.get("mode") == "sequential":
                last_index = (last_index + 1) % len(statuses)
                chosen = statuses[last_index]
            else:
                chosen = random.choice(statuses)

            status_text = chosen.get("text", "")

            # Only retrieve global statistics if dynamic placeholders are actually used in text
            if any(k in status_text for k in ("{event_count}", "{guild_count}", "{rsvp_count}")):
                stats = await _get_cached_stats()
                status_text = status_text.replace("{event_count}", str(stats.get("events", 0)))
                status_text = status_text.replace("{guild_count}", str(stats.get("guilds", 0)))
                status_text = status_text.replace("{rsvp_count}", str(stats.get("rsvps", 0)))

            # Map activity type
            type_map = {
                "playing": discord.ActivityType.playing,
                "watching": discord.ActivityType.watching,
                "listening": discord.ActivityType.listening,
                "competing": discord.ActivityType.competing
            }
            act_type = type_map.get(chosen.get("type", "watching"), discord.ActivityType.watching)

            activity = discord.Activity(
                type=act_type,
                name=status_text
            )
            await bot.change_presence(activity=activity, status=discord.Status.online)
            log.info("[Presence] Updated to: %s - %s", act_type.name, status_text)

        except Exception as e:
            log.error("[Presence] Error updating status: %s", e, exc_info=True)

        # Sleep interval (default 30s, minimum 15s to prevent Discord API rate limits)
        sleep_time = max(15, config.get("time", 30) if "config" in locals() and isinstance(config, dict) else 30)
        await asyncio.sleep(sleep_time)

def start_presence_task(bot: discord.Client) -> asyncio.Task:
    """Spawns the presence rotator background task on the bot's event loop."""
    return bot.loop.create_task(run_presence_rotator(bot))
