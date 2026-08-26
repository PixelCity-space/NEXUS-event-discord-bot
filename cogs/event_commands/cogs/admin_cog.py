import traceback
import discord
from discord.ext import commands
from discord import app_commands, ui
import database
from utils.auth import is_admin
from utils.i18n import t, load_guild_translations
from utils.logger import log
from utils.emoji_utils import make_button
from ..views.audit import ReliabilityAuditView

class AdminCommands(commands.GroupCog, name="admin"):
    """Cog for server administrators to manage server settings and audits."""
    
    def __init__(self, bot):
        self.bot = bot

    check_group = app_commands.Group(name="check", description="Audit checks for administrators")

    @check_group.command(name="no-show", description="Check member reliability scores (no-shows)")
    @app_commands.describe(
        event_id="Check the reliability of all participants in a specific event",
        all_time="Show a global leaderboard of all users with no-shows in this guild"
    )
    async def admin_check_noshow(self, interaction: discord.Interaction, event_id: str = None, all_time: bool = False):
        await interaction.response.defer(ephemeral=True)
        log.info(f"[Audit Debug] START: event_id={event_id}, all_time={all_time}")
        
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        
        if not await is_admin(interaction):
            return await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            
        if not event_id and not all_time:
            return await interaction.followup.send(t("MSG_AUDIT_HINT", guild_id=guild_id), ephemeral=True)

        try:
            if event_id:
                stats = await database.get_event_reliability_audit(event_id, guild_id)
                title = t("LBL_AUDIT_TITLE_EVENT", guild_id=guild_id).replace("{event_id}", str(event_id))
                filtered_stats = stats 
            else:
                stats = await database.get_guild_reliability_stats(guild_id, all_time=True)
                title = t("LBL_AUDIT_TITLE_GLOBAL", guild_id=guild_id)
                filtered_stats = [s for s in stats if int(s.get("noshow_count") or 0) > 0]

            if not filtered_stats:
                return await interaction.followup.send(t("ERR_AUDIT_NO_DATA", guild_id=guild_id), ephemeral=True)
                
            view = ReliabilityAuditView(self.bot, interaction.guild, filtered_stats, title=title)
            await view.build()
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as e:
            log.error(f"[Audit] Command Error: {e}\n{traceback.format_exc()}")
            try:
                await interaction.followup.send(t('ERR_WIZARD_GENERAL', guild_id=guild_id).replace('{e}', str(e)), ephemeral=True)
            except Exception:
                pass

    @admin_check_noshow.autocomplete("event_id")
    async def check_noshow_autocomplete(self, interaction: discord.Interaction, current: str):
        events = await database.get_all_active_events(interaction.guild_id)
        choices = []
        for e in events:
            label = f"{e['title']} ({e['event_id']})"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=e['event_id']))
        return choices[:25]

    @app_commands.command(name="messages", description="Manage global bot messages and strings")
    async def admin_messages(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        try:
            await load_guild_translations(guild_id)
            if not await is_admin(interaction):
                return await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            
            from cogs.message_wizard import MessageWizardView
            view = MessageWizardView(self.bot, interaction.guild.id)
            await view.prepare(interaction)
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as e:
            log.error(f"Error in admin_messages: {e}")
            await interaction.followup.send(f"{t('ERR_CRITICAL_WIZARD', guild_id=interaction.guild_id)}: `{e}`", ephemeral=True)

    @app_commands.command(name="emojis", description="Manage customized emoji sets for this server")
    async def manage_emojis(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        try:
            await load_guild_translations(guild_id)
            if not await is_admin(interaction):
                return await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            
            from cogs.emoji_wizard import EmojiWizardView
            view = EmojiWizardView(self.bot, interaction.guild_id)
            await view.refresh_message(interaction)
        except Exception as e:
            await interaction.followup.send(f"{t('ERR_CRITICAL_EMOJI', guild_id=interaction.guild_id)}: `{e}`", ephemeral=True)

    @app_commands.command(name="reset", description="WIPE ALL DATA for this server")
    async def reset(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)

        view = ui.View()
        confirm_btn = make_button(label=t("BTN_RESET_CONFIRM", guild_id=guild_id), style=discord.ButtonStyle.danger)
        cancel_btn = make_button(label=t("BTN_CANCEL", guild_id=guild_id), style=discord.ButtonStyle.secondary)

        async def confirm_callback(it: discord.Interaction):
            try:
                await database.reset_guild_data(it.guild.id)
                await it.response.send_message(t("MSG_RESET_SUCCESS", guild_id=it.guild_id), ephemeral=True)
            except Exception as e:
                await it.response.send_message(f"{t('ERR_RESET_FAILED', guild_id=it.guild_id)}: `{e}`", ephemeral=True)

        async def cancel_callback(it: discord.Interaction):
            await it.response.send_message(t("MSG_RESET_CANCELLED", guild_id=it.guild_id), ephemeral=True)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        await interaction.response.send_message(t("MSG_RESET_WARNING", guild_id=guild_id), view=view, ephemeral=True)
