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
        active_events = await database.get_all_active_events()

        for db_event in active_events:
            # 1. Lobby Expiration
            try:
                await handle_lobby_expiry(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    f"[Scheduler] Lobby expiry error for {db_event['event_id']}: {e}",
                    guild_id=db_event.get("guild_id"),
                )

            # 2. Multi-slot Reminders
            try:
                await handle_reminders(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    f"[Scheduler] Error handling reminders for {db_event['event_id']}: {e}", 
                    guild_id=db_event.get("guild_id")
                )

            # 3. Temporary Role Cleanup
            try:
                await check_role_cleanup(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    f"[Scheduler] Error cleaning roles for {db_event['event_id']}: {e}", 
                    guild_id=db_event.get("guild_id")
                )

            # 4. Series Recurring Reposting
            try:
                await handle_reposting(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    f"[Scheduler] Error handling reposting for {db_event['event_id']}: {e}", 
                    guild_id=db_event.get("guild_id")
                )

            # 5. Event Lifecycle Completion / Auto-archive
            try:
                await handle_event_completion(self.bot, db_event, now)
            except Exception as e:
                log.error(
                    f"[Scheduler] Error handling completion for {db_event['event_id']}: {e}", 
                    guild_id=db_event.get("guild_id")
                )

    @check_events.before_loop
    async def before_check_events(self):
        await self.bot.wait_until_ready()
