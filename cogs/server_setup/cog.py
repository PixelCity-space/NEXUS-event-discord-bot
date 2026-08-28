import discord
from discord import app_commands
from discord.ext import commands
from utils.auth import is_admin
from utils.i18n import t, load_guild_translations
from utils.logger import log
from .views.main_menu import ServerSetupView

class ServerSetupCog(commands.Cog, name="ServerSetup"):
    """Cog handling server configuration and default event settings."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure server-wide default values and admin settings")
    async def admin_setup(self, interaction: discord.Interaction):
        """Open the visual console for server configuration and event defaults."""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        if not guild_id:
            return await interaction.followup.send(t("ERR_GUILD_ONLY"), ephemeral=True)

        try:
            await load_guild_translations(guild_id)
            
            if not await is_admin(interaction):
                return await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
                
            view = ServerSetupView(self.bot, guild_id)
            await view.prepare(interaction)
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as e:
            log.error(f"[ServerSetupCog] Error in /setup command: {e}", exc_info=True)
            await interaction.followup.send(
                f"{t('ERR_CRITICAL_SETUP', guild_id=guild_id)}: `{e}`", 
                ephemeral=True
            )
