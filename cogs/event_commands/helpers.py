from typing import Optional
import discord
import database
from utils.auth import is_admin
from utils.i18n import t
from services.event_service import resolve_target_events, update_event_time_parsed

async def handle_status_change(
    bot: discord.Client, 
    interaction: discord.Interaction, 
    event_id: str, 
    status: str, 
    notify_type: str, 
    occurrence: Optional[int] = None, 
    new_time: Optional[str] = None
) -> None:
    """Handles status changes (cancelled, postponed, active) with series confirmation handling."""
    if not await is_admin(interaction):
        await interaction.response.send_message(t("ERR_ADMIN_ONLY"), ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    db_event, matched_events, _ = await resolve_target_events(event_id, interaction.guild_id, occurrence)
    if not db_event:
        await interaction.followup.send(
            t("ERR_EV_NOT_FOUND", guild_id=interaction.guild_id), ephemeral=True
        )
        return

    target_event_id = db_event["event_id"]

    if status == "postponed" and new_time:
        try:
            await update_event_time_parsed(target_event_id, new_time)
        except Exception as e:
            await interaction.followup.send(t("ERR_INVALID_TIME", guild_id=interaction.guild_id, e=str(e)), ephemeral=True)
            return

    series_events = (
        await database.get_active_events_by_config(db_event["config_name"], interaction.guild_id) 
        if db_event.get("config_name") and db_event["config_name"] != "manual" else []
    )
    if len(series_events) > 1 and not occurrence:
        from cogs.event_ui import StatusChoiceView
        msg = t("MSG_SERIES_STATUS_CONFIRM", guild_id=interaction.guild_id, status=status)
        view = StatusChoiceView(bot, target_event_id, db_event, series_events, status, notify_type)
        await interaction.followup.send(msg, view=view, ephemeral=True)
        return

    await database.update_event_status(target_event_id, status)
    await interaction.followup.send(t("MSG_STATUS_UPDATED", guild_id=interaction.guild_id, status=status), ephemeral=True)
