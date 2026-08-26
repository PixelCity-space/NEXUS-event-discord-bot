import json
import discord
from discord import ui
import database
from utils.i18n import t
from utils.logger import log

class AdvancedSettingsModal(ui.Modal):
    """Modal for configuring advanced event settings (e.g. waiting list limit)."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_ADVANCED_SETTINGS", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        data = wizard_view.data
        self.wait_limit_input = ui.TextInput(
            label=t("LBL_WAITLIST_LIMIT", guild_id=wizard_view.guild_id), 
            default=str(data.get("waiting_list_limit") or 0), 
            required=False
        )
        self.add_item(self.wait_limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = str(self.wait_limit_input.value)
        wait_limit = int(val) if val.isdigit() else 0
        extra = self.wizard_view.data.get("extra_data")
        if not extra:
            extra = {}
        elif isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        if not isinstance(extra, dict):
            extra = {}
        extra["waiting_list_limit"] = wait_limit
        self.wizard_view.data["extra_data"] = json.dumps(extra)
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class RoleLimitsModal(ui.Modal):
    """Modal for configuring specific capacity limits per role in the active icon set."""
    
    def __init__(self, wizard_view, icon_set_data):
        super().__init__(title=t("MODAL_ROLE_LIMITS", guild_id=wizard_view.guild_id)[:45])
        self.wizard_view = wizard_view
        self.options = icon_set_data.get("options", [])
        
        extra_data = wizard_view.data.get("extra_data")
        existing_limits = {}
        if extra_data:
            try:
                d = json.loads(extra_data) if isinstance(extra_data, str) else extra_data
                if isinstance(d, dict):
                    existing_limits = d.get("role_limits", {})
            except Exception as e:
                log.debug("RoleLimitsModal extra_data: %s", e)
            
        lines = []
        for opt in self.options:
            rid = opt["id"]
            lim = existing_limits.get(rid, opt.get("max_slots", 0))
            emoji = opt.get("emoji", "")
            lines.append(f"{emoji} {rid}: {lim}".strip())
            
        self.limits_input = ui.TextInput(
            label=t("LBL_ROLE_LIMITS_FORMAT", guild_id=wizard_view.guild_id)[:45],
            style=discord.TextStyle.paragraph,
            default="\n".join(lines),
            required=False,
        )
        self.add_item(self.limits_input)

    async def on_submit(self, interaction: discord.Interaction):
        role_limits = {}
        lines = str(self.limits_input.value).split("\n")
        for line in lines:
            if ":" not in line:
                continue
            left, right = line.rsplit(":", 1)
            right = right.strip()
            matched_id = None
            for opt in self.options:
                if opt["id"] in left:
                    matched_id = opt["id"]
                    break
            if matched_id and right.isdigit():
                role_limits[matched_id] = int(right)
                
        extra = self.wizard_view.data.get("extra_data")
        if not extra:
            extra = {}
        elif isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except Exception:
                extra = {}
        if not isinstance(extra, dict):
            extra = {}
        extra["role_limits"] = role_limits
        self.wizard_view.data["extra_data"] = json.dumps(extra)
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class RsvpRolesModal(ui.Modal):
    """Comma-separated role IDs; OR logic; empty = everyone can RSVP (stored on active_events)."""

    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_RSVP_ROLES", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        gid = wizard_view.guild_id
        cur = database.normalize_rsvp_allowed_role_ids_value(wizard_view.data.get("rsvp_allowed_role_ids"))
        self.roles_input = ui.TextInput(
            label=t("LBL_RSVP_ALLOWED_ROLES", guild_id=gid)[:45],
            placeholder=t("PH_RSVP_ALLOWED_ROLES", guild_id=gid)[:45],
            default=cur,
            style=discord.TextStyle.paragraph,
            max_length=400,
            required=False,
        )
        self.add_item(self.roles_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard_view.data["rsvp_allowed_role_ids"] = database.normalize_rsvp_allowed_role_ids_value(
            self.roles_input.value
        )
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)
