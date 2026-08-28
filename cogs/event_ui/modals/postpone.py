import discord
from dateutil import parser, tz
import database
from database import DEFAULT_TIMEZONE
from utils.emojis import PING, SYNC
from utils.i18n import t
from ..notifications import send_status_notification

class PostponeModal(discord.ui.Modal):
    """Modal for postponing or rescheduling an event with new date/time inputs."""
    
    def __init__(self, bot, event_id: str, parent_view, guild_id: int):
        super().__init__(title=t("MODAL_POSTPONE_TITLE", guild_id=guild_id), timeout=300)
        self.bot = bot
        self.event_id = event_id
        self.parent_view = parent_view
        
        self.start_input = discord.ui.TextInput(
            label=t("MODAL_POSTPONE_START", guild_id=guild_id),
            placeholder=t("PH_POSTPONE_START_EXAMPLE", guild_id=guild_id),
            required=False
        )
        self.add_item(self.start_input)
        
        self.end_input = discord.ui.TextInput(
            label=t("MODAL_POSTPONE_END", guild_id=guild_id),
            placeholder=t("PH_POSTPONE_END_EXAMPLE", guild_id=guild_id),
            required=False
        )
        self.add_item(self.end_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        local_tz = tz.gettz(DEFAULT_TIMEZONE)

        row = await database.get_active_event(self.event_id)
        if not row:
            return await interaction.followup.send(
                t("ERR_EV_NOT_FOUND", guild_id=interaction.guild_id), ephemeral=True
            )
        db_event = dict(row)

        # Empty start time means postpone without setting a new card
        if not self.start_input.value.strip():
            db_event["status"] = "postponed"
            await database.update_active_event(self.event_id, db_event)
            
            if not self.parent_view.event_conf:
                self.parent_view.event_conf = {}
            self.parent_view.event_conf["status"] = "postponed"
            await self.parent_view.prepare()
            
            for child in self.parent_view.children:
                if isinstance(child, discord.ui.Container):
                    for row_item in child.children:
                        if isinstance(row_item, discord.ui.ActionRow):
                            for item in row_item.children:
                                if isinstance(item, discord.ui.Button) and not item.custom_id.startswith("resched_"):
                                    item.disabled = True
                                    
            if interaction.message:
                await interaction.message.edit(view=self.parent_view)
            
            await send_status_notification(self.bot, self.event_id, db_event, "postponed", interaction.guild_id)
            
            return await interaction.followup.send(
                t("MSG_STATUS_UPDATED", guild_id=interaction.guild_id, status="postponed"),
                ephemeral=True,
            )

        try:
            start_dt = parser.parse(self.start_input.value).replace(tzinfo=local_tz)
            start_ts = int(start_dt.timestamp())
        except Exception:
            return await interaction.followup.send(
                t("ERR_INVALID_START", guild_id=interaction.guild_id),
                ephemeral=True,
            )
            
        end_ts = None
        if self.end_input.value:
            try:
                end_dt = parser.parse(self.end_input.value).replace(tzinfo=local_tz)
                end_ts = int(end_dt.timestamp())
            except Exception:
                return await interaction.followup.send(
                    t("ERR_INVALID_END", guild_id=interaction.guild_id),
                    ephemeral=True,
                )
        
        db_event["start_time"] = start_ts
        if end_ts:
            db_event["end_time"] = end_ts
        db_event["status"] = "rescheduled"
        await database.update_active_event(self.event_id, db_event)
        
        if not self.parent_view.event_conf:
            self.parent_view.event_conf = {}
        self.parent_view.event_conf["status"] = "rescheduled"
        self.parent_view.event_conf["start_time"] = start_ts
        if end_ts:
            self.parent_view.event_conf["end_time"] = end_ts
            
        await self.parent_view.prepare()
        for child in self.parent_view.children:
            if isinstance(child, discord.ui.Container):
                for row_item in child.children:
                    if isinstance(row_item, discord.ui.ActionRow):
                        for item in row_item.children:
                            if isinstance(item, discord.ui.Button):
                                item.disabled = True
                            
        if interaction.message:
            await interaction.message.edit(view=self.parent_view)

        # Post the new rescheduled active card
        channel = await self.bot.fetch_channel(int(db_event["channel_id"]))
        from ..views.dynamic_card import DynamicEventView
        new_view = DynamicEventView(self.bot, self.event_id, db_event)
        await new_view.prepare()
        
        ping_role_id = db_event.get("ping_role")
        ping_prefix = ""
        if ping_role_id and str(ping_role_id).isdigit() and int(ping_role_id) > 0:
            ping_prefix = f"{PING} <@&{ping_role_id}> "
            
        new_msg = await channel.send(
            content=f"{ping_prefix}{SYNC} **{t('MSG_RESCHEDULED_BROADCAST', guild_id=interaction.guild_id)}**",
            view=new_view,
        )
        await database.set_event_message(self.event_id, new_msg.id)
        
        # DM participants
        rsvps = await database.get_rsvps(self.event_id)
        notification_msg = f"{PING} {t('MSG_RESCHEDULED_BROADCAST', guild_id=interaction.guild_id)}"
        
        notify_type = await database.get_guild_setting(interaction.guild_id, "status_notification_type", default="none")
        notify_type = (notify_type or "none").lower()
        if notify_type in ["dm", "both"]:
            for uid, s in rsvps:
                try:
                    user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                    if user:
                        await user.send(notification_msg)
                except Exception:
                    pass
        
        await interaction.followup.send(
            t("MSG_RESCHEDULE_DONE", guild_id=interaction.guild_id),
            ephemeral=True,
        )
