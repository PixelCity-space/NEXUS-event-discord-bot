"""
Master Commands package for Nexus bot containing owner-only hub and bot maintenance commands.
"""

from .cog import MasterCommands
from .views import MasterPresenceView, PresenceEditView
from .modals import PresenceConfigModal, StatusModal

async def setup(bot):
    """Extension entry point for Discord.py."""
    await bot.add_cog(MasterCommands(bot))

__all__ = [
    "setup",
    "MasterCommands",
    "MasterPresenceView",
    "PresenceEditView",
    "PresenceConfigModal",
    "StatusModal",
]
