import traceback
import discord
from discord.ext import commands
from discord import app_commands, ui
import database
from utils.auth import is_admin
from utils.i18n import t, load_guild_translations, invalidate_guild_cache
from utils.logger import log
from utils.emoji_utils import make_button
from ..views.audit import ReliabilityAuditView


class ConfirmResetView(ui.View):
    """Secure confirmation view enforcing author-only and admin permissions."""

    def __init__(self, author_id: int, guild_id: int, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id or not await is_admin(interaction):
            await interaction.response.send_message(
                t("ERR_ADMIN_ONLY", guild_id=interaction.guild_id or self.guild_id),
                ephemeral=True,
            )
            return False
        return True


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
        events = await database.get_active_events(interaction.guild_id)
        choices = []
        for e in events:
            label = f"{e['title']} ({e['event_id']})"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=e['event_id']))
        return choices[:25]

    @app_commands.command(name="reset", description="WIPE ALL DATA for this server")
    async def reset(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)

        target_gid_int = int(guild_id) if guild_id else 0
        view = ConfirmResetView(author_id=interaction.user.id, guild_id=target_gid_int)
        confirm_btn = make_button(label=t("BTN_RESET_CONFIRM", guild_id=guild_id), style=discord.ButtonStyle.danger)
        cancel_btn = make_button(label=t("BTN_CANCEL", guild_id=guild_id), style=discord.ButtonStyle.secondary)

        async def confirm_callback(it: discord.Interaction):
            target_gid = it.guild.id if it.guild else target_gid_int
            try:
                await database.reset_guild_data(target_gid)
                invalidate_guild_cache(target_gid)
                await it.response.send_message(t("MSG_RESET_SUCCESS", guild_id=it.guild_id or guild_id), ephemeral=True)
            except Exception as e:
                await it.response.send_message(f"{t('ERR_RESET_FAILED', guild_id=it.guild_id or guild_id)}: `{e}`", ephemeral=True)

        async def cancel_callback(it: discord.Interaction):
            await it.response.send_message(t("MSG_RESET_CANCELLED", guild_id=it.guild_id or guild_id), ephemeral=True)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        await interaction.response.send_message(t("MSG_RESET_WARNING", guild_id=guild_id), view=view, ephemeral=True)

