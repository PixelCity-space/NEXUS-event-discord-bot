import discord
from discord import ui
from utils.emojis import ERROR
from utils.logger import log

class BaseSetupView(ui.LayoutView):
    """Base class for server setup views providing unified navigation and error handling."""
    
    def __init__(self, bot, guild_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild_id = guild_id

    async def prepare(self, interaction: discord.Interaction):
        """Asynchronously build UI components. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement the prepare() method.")

    async def navigate_to(self, view_target, interaction: discord.Interaction, **kwargs):
        """Convenience helper to transition smoothly to another setup view (by class or registry name)."""
        if isinstance(view_target, str):
            from .views.registry import get_view
            view_cls = get_view(view_target)
            if not view_cls:
                raise ValueError(f"Unknown setup view target: {view_target}")
        else:
            view_cls = view_target
        target_view = view_cls(self.bot, self.guild_id, **kwargs)
        await target_view.refresh_message(interaction)

    async def refresh_message(self, interaction: discord.Interaction):
        """Standard interaction refresh: prepare self and update the message with error handling."""
        try:
            await self.prepare(interaction)
            
            if interaction.response.is_done():
                await interaction.edit_original_response(view=self)
            elif interaction.type == discord.InteractionType.component:
                await interaction.response.edit_message(view=self)
            else:
                await interaction.response.send_message(view=self, ephemeral=True)
        except Exception as e:
            log.error(f"[{self.__class__.__name__}] refresh error: {e}", exc_info=True)
            msg = f"{ERROR} {e}"
            if not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.followup.send(msg, ephemeral=True)
