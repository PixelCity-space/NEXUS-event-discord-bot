import traceback
import discord
from discord.ext import commands
from discord import app_commands
import database
from utils.i18n import t
from utils.auth import is_admin
from utils.logger import log
from services.attendance_service import (
    get_eligible_attendance_participants,
    search_attendance_events_autocomplete,
)
from ..views.attendance_view import AttendanceView

class AttendanceCog(commands.Cog):
    """Cog for administrators to manage and audit event attendance."""
    
    def __init__(self, bot):
        self.bot = bot
        
    attendance_group = app_commands.Group(name="attendance", description="Manage event attendance")
    
    @attendance_group.command(name="manage", description="Track who showed up for a recent event")
    @app_commands.describe(event_id="The ID of the event to manage")
    async def manage_attendance(self, interaction: discord.Interaction, event_id: str):
        await interaction.response.defer(ephemeral=True)
        log.info(f"[Attendance Debug] COMMAND START: Event {event_id}")
        guild_id = interaction.guild_id
        
        try:
            if not await is_admin(interaction):
                await interaction.followup.send(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
                return
                
            db_event = await database.get_active_event(event_id, guild_id)
            if not db_event:
                pool = await database.get_pool()
                db_event = await pool.fetchrow("SELECT * FROM active_events WHERE event_id = $1 AND guild_id = $2", event_id, str(guild_id))
                
            if not db_event:
                await interaction.followup.send(t("ERR_EV_NOT_FOUND", guild_id=guild_id), ephemeral=True)
                return
                
            eligible = await get_eligible_attendance_participants(event_id, db_event["icon_set"])
            if not eligible:
                await interaction.followup.send(t("ERR_ATT_NO_RSVPS", guild_id=guild_id), ephemeral=True)
                return
                
            view = AttendanceView(self.bot, event_id, eligible, guild_id, title=db_event.get("title", t("LBL_EVENT", guild_id=guild_id)))
            await view.build()
            
            log.info(f"[Attendance Debug] COMMAND SUCCESS: Sending View")
            await interaction.followup.send(view=view, ephemeral=True)
            
        except Exception as e:
            log.error(f"[Attendance] Command Error: {e}\n{traceback.format_exc()}")
            try:
                await interaction.followup.send(t('ERR_WIZARD_GENERAL', guild_id=guild_id).replace('{e}', str(e)), ephemeral=True)
            except Exception:
                pass

    @manage_attendance.autocomplete("event_id")
    async def attendance_autocomplete(self, interaction: discord.Interaction, current: str):
        return await search_attendance_events_autocomplete(interaction.guild_id, current)
