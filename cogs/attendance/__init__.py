"""
Attendance package for Nexus bot managing event attendance tracking and no-show audits.
"""

from .cogs import AttendanceCog
from .views import AttendanceView

async def setup(bot):
    """Extension entry point for Discord.py."""
    await bot.add_cog(AttendanceCog(bot))

__all__ = [
    "setup",
    "AttendanceCog",
    "AttendanceView",
]
