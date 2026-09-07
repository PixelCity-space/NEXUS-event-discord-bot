import datetime
from dateutil import tz
import discord
import database
from database import DEFAULT_TIMEZONE
from utils.auth import is_admin
from utils.i18n import t
from utils.logger import log
from utils.extra_data import parse_extra_data
from ..config import get_event_conf, get_active_set
from ..card_builder import build_card_container, build_card_buttons, update_button_states
from ..rsvp_manager import handle_rsvp as rsvp_handler, try_promote_waiting as promote_handler
from ..notifications import send_status_notification, notify_promotion as notify_promotion_fn
from ..modals.postpone import PostponeModal

class DynamicEventView(discord.ui.LayoutView):
    """Dynamic Discord UI Components V2 interactive event card."""
    
    def __init__(self, bot, event_id: str, event_conf: dict = None, is_preview: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.event_id = event_id
        self.event_conf = event_conf
        self.is_preview = is_preview
        
        icon_set_key = "standard"
        if event_conf:
            icon_set_key = event_conf.get("icon_set", "standard")
        
        self.active_set = get_active_set(icon_set_key).copy()
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if getattr(self, "is_preview", False):
            await interaction.response.send_message(t("MSG_SAVED_PREVIEW", guild_id=interaction.guild_id), ephemeral=True)
            return False
        return True
        
    async def prepare(self):
        """Builds the complete V2 event card with TextDisplay content and buttons."""
        self.clear_items()
        
        db_event = await database.get_active_event(self.event_id)
        if db_event and not self.event_conf:
            self.event_conf = get_event_conf(db_event["config_name"])
            if not self.event_conf:
                self.event_conf = dict(db_event)
                ex_dto = parse_extra_data(db_event.get("extra_data"))
                self.event_conf.update(ex_dto.to_dict())

        if db_event:
            merged = dict(self.event_conf or {})
            if db_event.get("guild_id"):
                merged["guild_id"] = db_event["guild_id"]
            merged["lobby_mode"] = bool(db_event.get("lobby_mode"))
            v = db_event.get("lobby_remind_on_fill")
            merged["lobby_remind_on_fill"] = True if v is None else bool(v)
            merged["lobby_expires_at"] = db_event.get("lobby_expires_at")
            merged["start_time"] = db_event.get("start_time")
            merged["end_time"] = db_event.get("end_time")
            merged["status"] = db_event.get("status") or merged.get("status") or "active"
            if db_event.get("max_accepted") is not None:
                merged["max_accepted"] = db_event["max_accepted"]
            self.event_conf = merged

        event_conf = self.event_conf or {}
        rsvps = await database.get_rsvps(self.event_id)

        # 1. Build and add card container
        container = build_card_container(self.bot, self.event_id, event_conf, db_event, self.active_set, rsvps)
        self.add_item(container)

        # 2. Build and add button action rows
        button_rows = build_card_buttons(self, self.event_id, event_conf, db_event, self.active_set, rsvps)
        for r in button_rows:
            self.add_item(r)

        # 3. Update button disabled states based on limits and status
        status_cfg = event_conf.get("status", "active")
        update_button_states(self, rsvps, event_conf, self.active_set, ui_status=status_cfg)

    def update_button_states(self, rsvps_list: list, event_conf: dict, ui_status: str = None):
        """Disables buttons if limits are reached OR if status is inactive."""
        update_button_states(self, rsvps_list, event_conf, self.active_set, ui_status=ui_status)

    async def edit_callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not await is_admin(interaction):
            await interaction.response.send_message(t("ERR_ADMIN_ONLY", guild_id=guild_id), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        db_event = await database.get_active_event(self.event_id)
        if not db_event:
            await interaction.followup.send(
                t("ERR_EV_NOT_FOUND", guild_id=guild_id), ephemeral=True
            )
            return

        config_name = db_event.get("config_name")
        if config_name and config_name != "manual":
            series_events = await database.get_active_events_by_config(config_name, interaction.guild_id)
            if len(series_events) > 1:
                from .edit_choice import EditChoiceView
                view = EditChoiceView(self.bot, self.event_id, db_event, series_events)
                await interaction.followup.send(t("MSG_EDIT_SERIES_PROMPT", guild_id=guild_id), view=view, ephemeral=True)
                return

        await self._open_wizard(interaction, db_event)

    async def _open_wizard(self, interaction: discord.Interaction, db_event: dict, bulk_ids: list = None):
        local_tz = tz.gettz(db_event.get("timezone", DEFAULT_TIMEZONE))
        if db_event.get("start_time"):
            start_dt = datetime.datetime.fromtimestamp(db_event["start_time"], tz=local_tz)
            db_event["start_str"] = start_dt.strftime("%Y-%m-%d %H:%M")
        
        if db_event.get("end_time"):
            end_dt = datetime.datetime.fromtimestamp(db_event["end_time"], tz=local_tz)
            db_event["end_str"] = end_dt.strftime("%Y-%m-%d %H:%M")
        else:
            db_event["end_str"] = ""

        config_name = db_event.get("config_name")
        if db_event.get("lobby_mode"):
            wtype = "lobby"
        else:
            wtype = "single" if not config_name or config_name == "manual" else "series"
            
        from cogs.event_wizard import EventWizardView
        view = EventWizardView(
            self.bot, interaction.user.id, existing_data=db_event, is_edit=True, 
            guild_id=interaction.guild_id, bulk_ids=bulk_ids, wizard_type=wtype
        )
        await view.refresh_message(interaction, send_followup=True)

    async def postpone_callback(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_NO_PERM", guild_id=interaction.guild_id), ephemeral=True)
        await interaction.response.send_modal(PostponeModal(self.bot, self.event_id, self, interaction.guild_id))

    async def reschedule_callback(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_NO_PERM", guild_id=interaction.guild_id), ephemeral=True)
        await interaction.response.send_modal(PostponeModal(self.bot, self.event_id, self, interaction.guild_id))

    async def cancel_callback(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            return await interaction.response.send_message(t("ERR_NO_PERM", guild_id=interaction.guild_id), ephemeral=True)
        await interaction.response.defer()
        await database.update_event_status(self.event_id, "cancelled")
        if not self.event_conf:
            self.event_conf = {}
        self.event_conf["status"] = "cancelled"
        await self.prepare()
        for child in self.children:
            if isinstance(child, discord.ui.Container):
                for row_item in child.children:
                    if isinstance(row_item, discord.ui.ActionRow):
                        for item in row_item.children:
                            if isinstance(item, discord.ui.Button):
                                item.disabled = True
        await interaction.message.edit(view=self)
        db_ev = await database.get_active_event(self.event_id)
        if db_ev:
            await send_status_notification(self.bot, self.event_id, db_ev, "cancelled", interaction.guild_id)
        log.info(f"Event {self.event_id} cancelled by {interaction.user}")

    async def delete_callback(self, interaction: discord.Interaction):
        if not await is_admin(interaction):
            await interaction.response.send_message(t("ERR_NO_PERM", guild_id=interaction.guild_id), ephemeral=True)
            return
        await interaction.response.defer()
        
        # Temp role deletion
        db_event = await database.get_active_event(self.event_id, interaction.guild_id)
        if db_event:
            temp_role_id = db_event.get("temp_role_id")
            if temp_role_id:
                guild = interaction.guild
                if guild and guild.me.guild_permissions.manage_roles:
                    try:
                        role = guild.get_role(int(temp_role_id))
                        if role:
                            await role.delete(reason=f"Event {self.event_id} deleted by UI button ({interaction.user})")
                            log.info(f"[UI-Delete] Deleted temp role {temp_role_id} for event {self.event_id}")
                    except Exception as e:
                        log.error(f"[UI-Delete] Failed to delete role {temp_role_id}: {e}")

        await database.delete_active_event(self.event_id)
        if not self.event_conf:
            self.event_conf = {}
        self.event_conf["status"] = "deleted"
        
        new_view = DynamicEventView(self.bot, self.event_id, self.event_conf)
        await new_view.prepare()
        for child in new_view.children:
            if isinstance(child, discord.ui.Container):
                for row_item in child.children:
                    if isinstance(row_item, discord.ui.ActionRow):
                        for item in row_item.children:
                            if isinstance(item, discord.ui.Button):
                                item.disabled = True
        
        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, embeds=[], view=new_view)
        else:
            await interaction.response.edit_message(content=None, embeds=[], view=new_view)
        log.info(f"Event {self.event_id} deleted by {interaction.user}")

    async def handle_rsvp(self, interaction: discord.Interaction, status: str):
        await rsvp_handler(self, interaction, status)

    async def notify_promotion(self, interaction: discord.Interaction, user_id: int, opt: dict):
        await notify_promotion_fn(self.bot, interaction, self.event_id, self.event_conf or {}, user_id, opt)

    async def try_promote_waiting(self, interaction: discord.Interaction, db_event: dict, role_limits: dict, rsvps: list = None):
        await promote_handler(self.bot, self.event_id, self.event_conf or {}, self.active_set, interaction, db_event, role_limits, rsvps=rsvps)
