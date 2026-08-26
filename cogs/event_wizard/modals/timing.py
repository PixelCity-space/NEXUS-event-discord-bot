import re
import json
import discord
from discord import ui
from dateutil import parser
from database import DEFAULT_TIMEZONE
from utils.i18n import t
from utils.logger import log

class SingleEventSupplementaryModal(ui.Modal):
    """Step 2 for Single / Lobby: timezone + channel + ping role + (lobby_expire_offset or max_accepted)."""
    
    def __init__(self, wizard_view):
        gid = wizard_view.guild_id
        is_lobby = wizard_view.wizard_type == "lobby"
        super().__init__(title=t("MODAL_EVENT_SUPPLEMENTARY", guild_id=gid))
        self.wizard_view = wizard_view
        self.is_lobby = is_lobby
        data = wizard_view.data

        self.timezone_input = ui.TextInput(
            label=t("LBL_WIZ_TZ", guild_id=gid), 
            default=str(data.get("timezone") or DEFAULT_TIMEZONE), 
            required=True
        )
        self.channel_id_input = ui.TextInput(
            label=t("LBL_CHANNEL_ID", guild_id=gid), 
            placeholder=t("PH_CURRENT_CHANNEL", guild_id=gid), 
            default=str(data.get("channel_id") or ""), 
            required=False
        )
        self.ping_input = ui.TextInput(
            label=t("LBL_WIZ_PING", guild_id=gid), 
            default=str(data.get("ping_role") or ""), 
            required=False
        )

        if is_lobby:
            self.max_acc_input = None
            self.lobby_expire_input = ui.TextInput(
                label=t("LBL_LOBBY_EXPIRE_OFFSET", guild_id=gid),
                default=str(data.get("lobby_expire_offset") or "12h"),
                placeholder=t("PH_DURATION", guild_id=gid),
                required=True,
                max_length=24,
            )
            self.add_item(self.timezone_input)
            self.add_item(self.channel_id_input)
            self.add_item(self.lobby_expire_input)
            self.add_item(self.ping_input)
        else:
            self.lobby_expire_input = None
            self.max_acc_input = ui.TextInput(
                label=t("LBL_WIZ_MAX", guild_id=gid), 
                default=str(data.get("max_accepted") or 0), 
                required=False
            )
            self.add_item(self.timezone_input)
            self.add_item(self.max_acc_input)
            self.add_item(self.channel_id_input)
            self.add_item(self.ping_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard_view.data["timezone"] = str(self.timezone_input.value)
        self.wizard_view.data["channel_id"] = str(self.channel_id_input.value)
        self.wizard_view.data["ping_role"] = int(self.ping_input.value) if str(self.ping_input.value).isdigit() else 0
        
        if self.is_lobby:
            raw = str(self.lobby_expire_input.value).strip().lower() or "12h"
            if not re.match(r"^(\d+)([mhd])$", raw):
                return await interaction.response.send_message(
                    t("ERR_LOBBY_EXPIRE_OFFSET", guild_id=self.wizard_view.guild_id, e=raw),
                    ephemeral=True,
                )
            self.wizard_view.data["lobby_expire_offset"] = raw
        else:
            self.wizard_view.data["max_accepted"] = (
                int(self.max_acc_input.value) if str(self.max_acc_input.value).isdigit() else 0
            )
            if self.wizard_view.data["max_accepted"] == 0:
                self.wizard_view.data["use_waiting_list"] = False

        self.wizard_view.data["step2_opened"] = True
        self.wizard_view.steps_completed["step2"] = True
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class Step2Modal(ui.Modal):
    """Step 2 for Series: recurrence limit + repost offset interval."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_WIZARD_STEP2", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        data = wizard_view.data
        guild_id = wizard_view.guild_id
        
        self.repost_input = ui.TextInput(
            label=t("SETTING_REPOST_OFFSET", guild_id=guild_id), 
            placeholder=t("PH_DURATION", guild_id=guild_id), 
            default=str(data.get("repost_offset", "12h")), 
            required=False
        )
        self.limit_input = ui.TextInput(
            label=t("LBL_RECURRENCE_LIMIT", guild_id=guild_id), 
            default=str(data.get("recurrence_limit", 0)), 
            required=False
        )
        
        self.add_item(self.repost_input)
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard_view.data["repost_offset"] = str(self.repost_input.value)
        limit_val = str(self.limit_input.value).strip()
        if limit_val.isdigit():
            self.wizard_view.data["recurrence_limit"] = int(limit_val)
        else:
            try:
                dt = parser.parse(limit_val)
                extra = self.wizard_view.data.get("extra_data", {})
                if isinstance(extra, str): 
                    extra = json.loads(extra)
                extra["recurrence_limit_date"] = dt.timestamp()
                self.wizard_view.data["extra_data"] = json.dumps(extra)
                self.wizard_view.data["recurrence_limit"] = 0
            except Exception as e:
                log.debug("Step2Modal limit_date parse: %s", e)
                self.wizard_view.data["recurrence_limit"] = 0

        self.wizard_view.data["step2_opened"] = True
        self.wizard_view.steps_completed["step2"] = True
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class Step3Modal(ui.Modal):
    """Step 3 for Series: timezone + max accepted capacity + channel + ping role."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_WIZARD_STEP3", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        data = wizard_view.data
        guild_id = self.wizard_view.guild_id

        self.timezone_input = ui.TextInput(
            label=t("LBL_WIZ_TZ", guild_id=guild_id), 
            default=str(data.get("timezone") or DEFAULT_TIMEZONE), 
            required=True
        )
        self.max_acc_input = ui.TextInput(
            label=t("LBL_WIZ_MAX", guild_id=guild_id), 
            default=str(data.get("max_accepted") or 0), 
            required=False
        )
        self.channel_id_input = ui.TextInput(
            label=t("LBL_CHANNEL_ID", guild_id=guild_id), 
            placeholder=t("PH_CURRENT_CHANNEL", guild_id=guild_id), 
            default=str(data.get("channel_id") or ""), 
            required=False
        )
        self.ping_input = ui.TextInput(
            label=t("LBL_WIZ_PING", guild_id=guild_id), 
            default=str(data.get("ping_role") or ""), 
            required=False
        )

        self.add_item(self.timezone_input)
        self.add_item(self.max_acc_input)
        self.add_item(self.channel_id_input)
        self.add_item(self.ping_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard_view.data["timezone"] = str(self.timezone_input.value)
        self.wizard_view.data["max_accepted"] = int(self.max_acc_input.value) if str(self.max_acc_input.value).isdigit() else 0
        if self.wizard_view.data["max_accepted"] == 0:
            self.wizard_view.data["use_waiting_list"] = False
        self.wizard_view.data["channel_id"] = str(self.channel_id_input.value)
        self.wizard_view.data["ping_role"] = int(self.ping_input.value) if str(self.ping_input.value).isdigit() else 0
        
        self.wizard_view.data["step3_opened"] = True
        self.wizard_view.steps_completed["step3"] = True
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)
