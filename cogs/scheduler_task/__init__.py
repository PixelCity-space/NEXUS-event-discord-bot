"""
Scheduler Task package for Nexus bot executing background periodic jobs.
"""

from .cog import SchedulerTask
from .jobs import (
    handle_event_completion,
    handle_lobby_expiry,
    refresh_event_card,
    check_role_cleanup,
    handle_reminders,
    handle_reposting,
)

async def setup(bot):
    """Extension entry point for Discord.py."""
    await bot.add_cog(SchedulerTask(bot))

__all__ = [
    "setup",
    "SchedulerTask",
    "handle_event_completion",
    "handle_lobby_expiry",
    "refresh_event_card",
    "check_role_cleanup",
    "handle_reminders",
    "handle_reposting",
]
