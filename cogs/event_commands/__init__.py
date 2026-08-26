"""
Event Commands package for Nexus bot containing user, admin, and draft command groups.
"""

from .cogs import EventCommands, AdminCommands, DraftCommands
from .views import MyEventsView, EventHistoryView, ReliabilityAuditView, HelpView
from .helpers import handle_status_change

async def setup(bot):
    """Extension entry point for Discord.py to load all event command cogs."""
    await bot.add_cog(EventCommands(bot))
    await bot.add_cog(AdminCommands(bot))
    await bot.add_cog(DraftCommands(bot))

__all__ = [
    "setup",
    "EventCommands",
    "AdminCommands",
    "DraftCommands",
    "MyEventsView",
    "EventHistoryView",
    "ReliabilityAuditView",
    "HelpView",
    "handle_status_change",
]
