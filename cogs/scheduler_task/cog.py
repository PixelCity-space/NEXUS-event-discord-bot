import time
from discord.ext import commands, tasks
import database
from utils.logger import log
from .jobs import (
    handle_lobby_expiry,
    handle_reminders,
    check_role_cleanup,
    handle_reposting,
    handle_event_completion,
)

class SchedulerTask(commands.Cog):
    """Background recurring task cog executing periodic checks every minute."""
    
    def __init__(self, bot):
        self.bot = bot
        self.check_events.start()

    def cog_unload(self):
        self.check_events.cancel()

    @tasks.loop(minutes=1.0)
    async def check_events(self):
        """Main minute-loop iterating through all active events to trigger periodic jobs."""
        now = time.time()
        active_events = await database.get_active_events()
        if not active_events:
            return

        # PERF-001: Prefetch all active event reminders in a single O(1) batch query
        try:
            active_reminders_map = await database.get_all_active_reminders_batch()
        except Exception as e:
            log.error("[Scheduler] Failed to prefetch active reminders batch: %s", e)
            active_reminders_map = {}

        for db_event in active_events:
            eid = db_event["event_id"]

            # 1. Lobby Expiration
            try:
                await handle_lobby_expiry(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    "[Scheduler] Lobby expiry error for %s: %s", eid, e,
                    guild_id=db_event.get("guild_id"),
                )

            # 2. Multi-slot Reminders (using preloaded batch data)
            try:
                preloaded = active_reminders_map.get(eid, [])
                await handle_reminders(self.bot, db_event, now, preloaded_reminders=preloaded)
            except Exception as e:
                log.error(
                    "[Scheduler] Error handling reminders for %s: %s", eid, e,
                    guild_id=db_event.get("guild_id"),
                )

            # 3. Temporary Role Cleanup
            try:
                await check_role_cleanup(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    "[Scheduler] Error cleaning roles for %s: %s", eid, e,
                    guild_id=db_event.get("guild_id"),
                )

            # 4. Series Recurring Reposting
            try:
                await handle_reposting(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    "[Scheduler] Error handling reposting for %s: %s", eid, e,
                    guild_id=db_event.get("guild_id"),
                )

            # 5. Event Lifecycle Completion / Auto-archive
            try:
                await handle_event_completion(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    "[Scheduler] Error handling completion for %s: %s", eid, e,
                    guild_id=db_event.get("guild_id"),
                )

    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
