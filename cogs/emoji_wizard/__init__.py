"""
Emoji Wizard package for Nexus bot allowing custom emoji & role set configuration.
"""

from discord.ext import commands
from .views import (
    EmojiWizardView,
    TemplateChoiceView,
    ConfirmDeleteView,
    EmojiHelpView,
    send_emoji_help,
)
from .modals import EditEmojiSetModal

class EmojiWizardCog(commands.Cog):
    """Empty cog to satisfy discord.py requirements, views only."""
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    """Extension entry point for Discord.py."""
    await bot.add_cog(EmojiWizardCog(bot))

__all__ = [
    "setup",
    "EmojiWizardCog",
    "EmojiWizardView",
    "TemplateChoiceView",
    "ConfirmDeleteView",
    "EmojiHelpView",
    "send_emoji_help",
    "EditEmojiSetModal",
]
