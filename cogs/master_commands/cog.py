import platform
import discord
from discord import app_commands, ui
from discord.ext import commands
import database
from utils.auth import is_master
from utils.i18n import t
from utils.logger import log
from utils.config import config
from utils.templates import ICON_SET_TEMPLATES, get_template_data
from cogs.emoji_wizard import EmojiWizardView
from cogs.event_ui import load_custom_sets
from .views.presence_menu import MasterPresenceView

@app_commands.check(is_master)
class MasterCommands(commands.GroupCog, name="master"):
    """Global Bot Management commands. Only visible in the Master Guild."""
    
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="stats")
    async def stats(self, interaction: discord.Interaction):
        """View global bot usage and database statistics."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            db_stats = await database.get_global_stats()
            live_guilds = len(self.bot.guilds)
            bot_version = config.version

            body_text = (
                f"{t('MASTER_STATS_GUILDS', guild_id=None, val=live_guilds)}\n\n"
                f"{t('MASTER_STATS_EVENTS', guild_id=None, val=db_stats['events'])}\n\n"
                f"{t('MASTER_STATS_RSVPS', guild_id=None, val=db_stats['rsvps'])}\n\n"
                f"{t('MASTER_STATS_VERSION', guild_id=None, val=bot_version)}\n\n"
                f"{t('MASTER_STATS_PYTHON', guild_id=None, val=platform.python_version())}\n\n"
                f"{t('MASTER_STATS_LATENCY', guild_id=None, val=f'{round(self.bot.latency * 1000)}ms')}"
            )

            layout = ui.LayoutView()
            container = ui.Container(
                ui.TextDisplay(f"### {t('MASTER_STATS_TITLE', guild_id=None)}"),
                ui.Separator(),
                ui.TextDisplay(body_text),
                ui.Separator(),
                ui.TextDisplay(f"{t('MASTER_STATS_FOOTER', guild_id=None)}"),
                accent_color=0x40C4FF
            )
            layout.add_item(container)
            
            await interaction.followup.send(view=layout)
        except Exception as e:
            log.error(f"[Master] Error getting stats: {e}")
            await interaction.followup.send(t("MASTER_STATS_ERR", guild_id=None).replace("{e}", str(e)))

    @app_commands.command(name="status")
    async def status_mgmt(self, interaction: discord.Interaction):
        """Manage the bot's dynamic presence list using a visual console."""
        view = MasterPresenceView(self.bot)
        await view.refresh_message(interaction)

    @app_commands.command(name="global-sets")
    async def global_emoji_sets(self, interaction: discord.Interaction):
        """Manage system-wide global emoji sets used by all guilds."""
        try:
            view = EmojiWizardView(self.bot, None, is_global=True)
            await view.refresh_message(interaction)
        except Exception as e:
            log.error(f"[Master] Error in global-sets: {e}")
            err_msg = t("MASTER_EMOJI_ERR", guild_id=None).replace("{e}", str(e))
            if interaction.response.is_done():
                await interaction.followup.send(err_msg, ephemeral=True)
            else:
                await interaction.response.send_message(err_msg, ephemeral=True)

    @app_commands.command(name="reset-global-sets")
    async def reset_global_sets_cmd(self, interaction: discord.Interaction):
        """Reset all global emoji sets to match the hardcoded templates in utils/templates.py."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            await database.clear_global_emoji_sets()
            
            count = 0
            for tid, tmpl in ICON_SET_TEMPLATES.items():
                name = t(tmpl.get("label_key"), guild_id=None) if "label_key" in tmpl else tid
                data = get_template_data(tid)
                if data:
                    await database.save_global_emoji_set(tid, name, data)
                    count += 1
            
            await load_custom_sets()
            
            msg = (
                t("MSG_GLOBAL_RESETS_SUCCESS", guild_id=None, val=count)
                if count > 0
                else t("MSG_GLOBAL_RESETS_NONE", guild_id=None)
            )
            await interaction.followup.send(msg)
        except Exception as e:
            log.error(f"[Master] Error resetting global sets: {e}")
            await interaction.followup.send(t('ERR_MASTER_FOLLOWUP', guild_id=None, e=str(e)))
