import uuid
import discord
from discord import ui
from utils.emojis import ERROR
from utils.i18n import t
from utils.logger import log
from utils.text_utils import slugify

class SingleEventModal(ui.Modal):
    """Step 1 for Single Events & Lobbies (Basic title, description, time/capacity, images)."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_EVENT_BASIC", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        data = wizard_view.data
        guild_id = self.wizard_view.guild_id
        is_lobby = wizard_view.wizard_type == "lobby"

        self.title_input = ui.TextInput(
            label=t("LBL_WIZ_TITLE", guild_id=guild_id), 
            default=str(data.get("title") or ""), 
            required=True
        )
        self.desc_input = ui.TextInput(
            label=t("LBL_WIZ_DESC", guild_id=guild_id), 
            style=discord.TextStyle.paragraph, 
            default=str(data.get("description") or ""), 
            required=False
        )

        if is_lobby:
            self.max_acc_input = ui.TextInput(
                label=t("LBL_WIZ_MAX", guild_id=guild_id),
                default=str(data.get("max_accepted") or 0),
                required=False,
            )
            self.start_input = None
            self.end_input = None
        else:
            self.max_acc_input = None
            self.start_input = ui.TextInput(
                label=t("LBL_WIZ_START", guild_id=guild_id),
                placeholder="2026-05-15 18:00",
                default=str(data.get("start_str") or ""),
                required=True,
            )
            self.end_input = ui.TextInput(
                label=t("LBL_WIZ_END", guild_id=guild_id),
                placeholder="2026-05-15 20:00",
                default=str(data.get("end_str") or ""),
                required=False,
            )

        self.images_input = ui.TextInput(
            label=t("LBL_WIZ_IMAGES", guild_id=guild_id), 
            default=str(data.get("image_urls") or ""), 
            required=False
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        if is_lobby:
            self.add_item(self.max_acc_input)
        else:
            self.add_item(self.start_input)
            self.add_item(self.end_input)
        self.add_item(self.images_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            title = str(self.title_input.value)
            self.wizard_view.data["title"] = title
            self.wizard_view.data["config_name"] = "manual"
            self.wizard_view.data["description"] = str(self.desc_input.value)
            self.wizard_view.data["image_urls"] = str(self.images_input.value)

            if self.wizard_view.wizard_type == "lobby":
                self.wizard_view.data["start_str"] = ""
                self.wizard_view.data["end_str"] = ""
                self.wizard_view.data["max_accepted"] = (
                    int(self.max_acc_input.value) if str(self.max_acc_input.value).isdigit() else 0
                )
                if self.wizard_view.data["max_accepted"] == 0:
                    self.wizard_view.data["use_waiting_list"] = False
            else:
                self.wizard_view.data["start_str"] = str(self.start_input.value).strip()
                self.wizard_view.data["end_str"] = str(self.end_input.value).strip()

            self.wizard_view.steps_completed["step1"] = bool(title) and (
                self.wizard_view.wizard_type == "lobby" or bool(self.wizard_view.data.get("start_str"))
            )
            await self.wizard_view.save_to_draft()
            await self.wizard_view.refresh_message(interaction)
        except Exception as e:
            log.error(f"[Wizard] SingleEventModal on_submit error: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"{ERROR} {e}", ephemeral=True)

class Step1Modal(ui.Modal):
    """Step 1 for Recurring Event Series (Basic title, description, start time, end time, images)."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_WIZARD_STEP1", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        data = wizard_view.data
        guild_id = self.wizard_view.guild_id
        
        self.title_input = ui.TextInput(
            label=t("LBL_WIZ_TITLE", guild_id=guild_id), 
            default=str(data.get("title") or ""), 
            required=True
        )
        self.desc_input = ui.TextInput(
            label=t("LBL_WIZ_DESC", guild_id=guild_id), 
            style=discord.TextStyle.paragraph, 
            default=str(data.get("description") or ""), 
            required=False
        )
        self.start_input = ui.TextInput(
            label=t("LBL_WIZ_START", guild_id=guild_id),
            placeholder="2026-05-15 18:00",
            default=str(data.get("start_str") or ""),
            required=True,
        )
        self.end_input = ui.TextInput(
            label=t("LBL_WIZ_END", guild_id=guild_id),
            placeholder="2026-05-15 20:00",
            default=str(data.get("end_str") or ""),
            required=False,
        )
        self.images_input = ui.TextInput(
            label=t("LBL_WIZ_IMAGES", guild_id=guild_id), 
            default=str(data.get("image_urls") or ""), 
            required=False
        )
        
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.start_input)
        self.add_item(self.end_input)
        self.add_item(self.images_input)

    async def on_submit(self, interaction: discord.Interaction):
        title = str(self.title_input.value)
        self.wizard_view.data["title"] = title
        if not self.wizard_view.data.get("config_name") or self.wizard_view.data.get("config_name") == "manual":
            base_slug = slugify(title) or "ev"
            self.wizard_view.data["config_name"] = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        self.wizard_view.data["description"] = str(self.desc_input.value)
        self.wizard_view.data["image_urls"] = str(self.images_input.value)

        self.wizard_view.data["start_str"] = str(self.start_input.value).strip()
        self.wizard_view.data["end_str"] = str(self.end_input.value).strip()

        self.wizard_view.steps_completed["step1"] = bool(title) and bool(self.wizard_view.data.get("start_str"))
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)
