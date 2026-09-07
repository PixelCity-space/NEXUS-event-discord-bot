import discord
from discord.ext import commands
from discord import app_commands
import database
from utils.auth import is_admin, is_master, is_owner
from utils.i18n import t, load_guild_translations
from utils.logger import log
from utils.config import config
from utils.enums import EventStatus
from services.event_service import (
    resolve_target_events,
    search_events_autocomplete,
    remove_events_with_cleanup,
)
from services.export_service import (
    generate_events_csv,
    generate_rsvps_csv,
    create_csv_discord_file,
    generate_future_events_ics_file,
)
from cogs.event_wizard import WizardStartView, EventWizardView
from ..helpers import handle_status_change
from ..views.my_events import MyEventsView
from ..views.history import EventHistoryView
from ..views.help import HelpView

SUFFIX = config.command_suffix

class EventCommands(commands.Cog, name="EventCommands"):
    """Cog for general event management commands."""
    
    event_group = app_commands.Group(name="event", description="Event management commands")

    def __init__(self, bot):
        self.bot = bot

    @event_group.command(name="create", description="Start the interactive event creation wizard")
    async def create_event(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        
        if not await is_admin(interaction):
            await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            return

        try:
            view = WizardStartView(self.bot, interaction.user.id, guild_id=guild_id)
            await view.refresh_message(interaction)
        except Exception as e:
            log.error(f"Error starting wizard: {e}")
            await interaction.followup.send(f"{t('ERR_CRITICAL_WIZARD', guild_id=interaction.guild_id)}: `{e}`", ephemeral=True)

    @event_group.command(name="lobby", description="Create a fill-to-start lobby event (no fixed time until full)")
    async def create_lobby_event(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)

        if not await is_admin(interaction):
            await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            return

        try:
            view = EventWizardView(
                self.bot,
                interaction.user.id,
                guild_id=guild_id,
                wizard_type="lobby",
            )
            await view.refresh_message(interaction)
        except Exception as e:
            log.error(f"Error starting lobby wizard: {e}")
            await interaction.followup.send(
                f"{t('ERR_CRITICAL_WIZARD', guild_id=interaction.guild_id)}: `{e}`", ephemeral=True
            )

    @event_group.command(name="edit", description="Edit an existing event")
    @app_commands.describe(
        event_id="The short ID or series name of the event to edit",
        occurrence="Optional: which occurrence number of a series to edit (1, 2, 3...)"
    )
    async def edit_event(self, interaction: discord.Interaction, event_id: str, occurrence: int = None):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        
        if not await is_admin(interaction):
            await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            return
            
        db_event, matched_events, bulk_ids = await resolve_target_events(event_id, interaction.guild_id, occurrence)

        if not db_event:
            if event_id.startswith("series:") and occurrence is not None and matched_events and occurrence > len(matched_events):
                return await interaction.followup.send(
                    t("ERR_SERIES_COUNT", guild_id=interaction.guild_id, occurrence=occurrence),
                    ephemeral=True
                )
            await interaction.followup.send(
                t("ERR_EV_NOT_FOUND", guild_id=guild_id), ephemeral=True
            )
            return

        try:
            config_name = db_event.get("config_name")
            if db_event.get("lobby_mode"):
                wtype = "lobby"
            else:
                wtype = "single" if not config_name or config_name == "manual" else "series"
            view = EventWizardView(
                self.bot, interaction.user.id, existing_data=db_event, is_edit=True, 
                guild_id=interaction.guild_id, bulk_ids=bulk_ids, wizard_type=wtype
            )
            await view.refresh_message(interaction)
        except Exception as e:
            log.error(f"Error starting edit wizard: {e}")
            await interaction.followup.send(f"{t('ERR_CRITICAL_EDIT', guild_id=interaction.guild_id)}: `{e}`", ephemeral=True)

    @edit_event.autocomplete("event_id")
    async def edit_event_autocomplete(self, interaction: discord.Interaction, current: str):
        return await search_events_autocomplete(interaction.guild_id, current)

    @event_group.command(name="list", description="Show all active events")
    async def list_events(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(t("ERR_ADMIN_ONLY"), ephemeral=True)
            return

        events = await database.get_active_events(interaction.guild_id)
        if not events: 
            return await interaction.response.send_message(t("ERR_NO_ACTIVE_EVENTS", guild_id=interaction.guild_id), ephemeral=True)

        text = t("LBL_ACTIVE_EVENTS_LIST", guild_id=interaction.guild_id) + "\n"
        for ev in events:
            title = ev.get('title') or ev.get('config_name') or t("LBL_UNNAMED_EVENT", guild_id=interaction.guild_id)
            st = ev.get("start_time")
            if st is not None:
                text += f"- `{ev['event_id']}`: {title} (<t:{int(st)}:R>)\n"
            else:
                text += f"- `{ev['event_id']}`: {title} ({t('LBL_LOBBY_LIST_NO_START', guild_id=interaction.guild_id)})\n"
        await interaction.response.send_message(text, ephemeral=True)

    @event_group.command(name="cancel", description="Mark an event as CANCELLED")
    async def cancel_event(self, interaction: discord.Interaction, event_id: str, notify: str = "none", occurrence: int = None):
        await handle_status_change(self.bot, interaction, event_id, EventStatus.CANCELLED, notify, occurrence)

    @event_group.command(name="postpone", description="Mark an event as POSTPONED")
    async def postpone_event(self, interaction: discord.Interaction, event_id: str, new_time: str = None, notify: str = "none", occurrence: int = None):
        await handle_status_change(self.bot, interaction, event_id, EventStatus.POSTPONED, notify, occurrence, new_time)

    @event_group.command(name="activate", description="Set a cancelled/postponed event back to ACTIVE")
    async def activate_event(self, interaction: discord.Interaction, event_id: str, occurrence: int = None):
        await handle_status_change(self.bot, interaction, event_id, EventStatus.ACTIVE, "none", occurrence)

    @event_group.command(name="sheets", description="Export all event data to CSV for Google Sheets")
    async def sheets_export(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        
        if not await is_admin(interaction):
            return await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            
        try:
            events = await database.get_guild_events_export(guild_id)
            rsvps = await database.get_guild_rsvps_export(guild_id)
            
            e_csv = generate_events_csv(events)
            e_file = create_csv_discord_file(e_csv, filename=f"events_summary_{guild_id}.csv")
            
            r_csv = generate_rsvps_csv(rsvps)
            r_file = create_csv_discord_file(r_csv, filename=f"rsvps_details_{guild_id}.csv")
            
            await interaction.followup.send(
                t("MSG_SHEETS_EXPORT_READY", guild_id=guild_id),
                files=[e_file, r_file],
                ephemeral=True
            )
        except Exception as ex:
            log.error(f"Sheets export error: {ex}")
            await interaction.followup.send(t("ERR_WIZARD_GENERAL", guild_id=guild_id, e=ex), ephemeral=True)

    @event_group.command(name="ics", description="Export all future events to a .ics calendar file")
    async def ics_export(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        await load_guild_translations(guild_id)
        
        try:
            events = await database.get_active_events(guild_id)
            if not events:
                return await interaction.followup.send(t("ERR_NO_ACTIVE_EVENTS", guild_id=guild_id), ephemeral=True)
            
            ics_file = generate_future_events_ics_file(events, guild_id)
            if not ics_file:
                return await interaction.followup.send(t("ERR_NO_ACTIVE_EVENTS", guild_id=guild_id), ephemeral=True)
            
            await interaction.followup.send(
                t("MSG_ICS_EXPORT_READY", guild_id=guild_id),
                file=ics_file,
                ephemeral=True
            )
        except Exception as ex:
            log.error(f"ICS export error: {ex}")
            await interaction.followup.send(t("ERR_WIZARD_GENERAL", guild_id=guild_id, e=ex), ephemeral=True)

    @event_group.command(name="my-events", description="List all events you are organizing or attending")
    async def my_events(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await load_guild_translations(guild_id)
        
        try:
            events = await database.get_user_active_events(guild_id, user_id)
            if not events:
                return await interaction.followup.send(t("MSG_NO_MY_EVENTS", guild_id=guild_id), ephemeral=True)
            
            view = MyEventsView(self.bot, guild_id, user_id, events)
            await view.build()
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as ex:
            log.error(f"My events error: {ex}")
            await interaction.followup.send(t("ERR_WIZARD_GENERAL", guild_id=guild_id, e=ex), ephemeral=True)

    @event_group.command(name="end", description="Manually close an active event and move it to history")
    @app_commands.describe(event_id="The ID of the event to close")
    async def event_end(self, interaction: discord.Interaction, event_id: str):
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_ADMIN_ONLY"), ephemeral=True)
            
        await database.update_event_status(event_id, EventStatus.CLOSED)
        await interaction.response.send_message(t("MSG_EVENT_CLOSED", guild_id=interaction.guild_id, event_id=event_id), ephemeral=True)

    @event_end.autocomplete("event_id")
    async def end_autocomplete(self, interaction: discord.Interaction, current: str):
        events = await database.get_endable_events(interaction.guild_id)
        return [
            app_commands.Choice(name=f"{ev['title']} ({ev['event_id']})", value=ev["event_id"])
            for ev in events if current.lower() in ev["title"].lower() or current.lower() in ev["event_id"].lower()
        ][:25]

    @event_group.command(name="history", description="View your past event participation")
    async def event_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await load_guild_translations(guild_id)
        
        try:
            events = await database.get_user_event_history(guild_id, user_id)
            if not events:
                return await interaction.followup.send(t("MSG_NO_HISTORY", guild_id=guild_id), ephemeral=True)
            
            view = EventHistoryView(self.bot, guild_id, user_id, events)
            await view.build()
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception as ex:
            log.error(f"Event history error: {ex}")
            await interaction.followup.send(t("ERR_WIZARD_GENERAL", guild_id=guild_id, e=ex), ephemeral=True)

    @cancel_event.autocomplete("event_id")
    @postpone_event.autocomplete("event_id")
    @activate_event.autocomplete("event_id")
    async def status_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.edit_event_autocomplete(interaction, current)

    @event_group.command(name="remove", description="Delete an active event message")
    async def remove_event(self, interaction: discord.Interaction, event_id: str):
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_ADMIN_ONLY"), ephemeral=True)
        
        log.info(f"[Remove] Looking for event_id={event_id!r} guild_id={interaction.guild_id!r}")
        
        _, target_events, _ = await resolve_target_events(event_id, interaction.guild_id)

        if not target_events:
            return await interaction.response.send_message(t("ERR_EV_NOT_FOUND", guild_id=interaction.guild_id), ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        await remove_events_with_cleanup(self.bot, target_events, interaction.guild, actor=interaction.user)
        await interaction.followup.send(t("MSG_EVENT_REMOVED", guild_id=interaction.guild_id), ephemeral=True)

    @remove_event.autocomplete("event_id")
    async def remove_event_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.edit_event_autocomplete(interaction, current)

    # Prefix Synchronization Commands
    @commands.command(name="sync", aliases=["sync_nexus"])
    @commands.guild_only()
    async def sync_prefix(self, ctx: commands.Context, spec: str | None = None):
        if spec in ("global", "copy"):
            if not await is_owner(ctx):
                return await ctx.send(t("ERR_ADMIN_ONLY", guild_id=ctx.guild.id))
        else:
            if not (await is_master(ctx) or await is_admin(ctx)):
                return await ctx.send(t("ERR_ADMIN_ONLY", guild_id=ctx.guild.id))
        
        await ctx.send(t("SYNC_START", guild_id=ctx.guild.id))
        try:
            if spec == "global":
                synced = await self.bot.tree.sync()
                await ctx.send(t("SYNC_GLOBAL_OK", guild_id=ctx.guild.id).replace("{count}", str(len(synced))))
            elif spec == "copy":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(t("SYNC_COPY_OK", guild_id=ctx.guild.id).replace("{count}", str(len(synced))))
            else:
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(t("SYNC_GUILD_OK", guild_id=ctx.guild.id).replace("{count}", str(len(synced))))
        except Exception as e:
            await ctx.send(t("SYNC_FAILED", guild_id=ctx.guild.id).replace("{e}", str(e)))

    @commands.command(name="clear_commands", aliases=["clear_commands_nexus"])
    @commands.guild_only()
    async def clear_commands_prefix(self, ctx: commands.Context):
        # Destructive global action: strictly restricted to Bot Owner
        if not await is_owner(ctx):
            return await ctx.send(t("ERR_ADMIN_ONLY", guild_id=ctx.guild.id))
        
        await ctx.send(t("SYNC_CLEAR_START", guild_id=ctx.guild.id))
        try:
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync(guild=None)
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.send(t("SYNC_CLEAR_SUCCESS", guild_id=ctx.guild.id).replace("{suffix}", SUFFIX))
        except Exception as e:
            await ctx.send(t("SYNC_FAILED", guild_id=ctx.guild.id).replace("{e}", str(e)))

    @app_commands.command(name="help", description="Show a guide to all bot commands and features")
    async def show_help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await load_guild_translations(interaction.guild_id)
        
        view = HelpView(self.bot, interaction.guild_id)
        await view.build()
        await interaction.followup.send(view=view, ephemeral=True)
