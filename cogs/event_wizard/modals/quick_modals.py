import re
import discord
from discord import ui
import database
from utils.i18n import t

class ReminderOffsetModal(ui.Modal):
    """Modal for multi-line reminder offset configurations within the wizard."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_REMINDER_OFFSETS", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        ro = self.wizard_view.data.get("reminder_offsets")
        if isinstance(ro, list) and ro:
            dflt = "\n".join(ro[: database.MAX_EVENT_REMINDERS])
        else:
            dflt = str(self.wizard_view.data.get("reminder_offset", ""))
            
        self.inp = ui.TextInput(
            label=t("LBL_REMINDER_OFFSETS_PARAGRAPH", guild_id=wizard_view.guild_id),
            placeholder="15m,dm\n1h,ping,All\n2d,dm,Tank",
            default=dflt,
            style=discord.TextStyle.paragraph,
            max_length=400,
            required=False,
        )
        self.add_item(self.inp)

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = str(self.inp.value).strip()
        if not raw_val:
            # Empty modal disables reminders
            self.wizard_view.data["reminder_offsets"] = []
            self.wizard_view.data["reminder_type"] = "none"
            self.wizard_view.data["reminder_offset"] = "" 
            await self.wizard_view.save_to_draft()
            return await self.wizard_view.refresh_message(interaction)

        lines = [x.strip() for x in raw_val.splitlines() if x.strip()]
        
        # Regex validation
        valid_pattern = re.compile(r"^(\d+)([mhd])(?:,([^,]*))?(?:,(.*))?$", re.IGNORECASE)
        for line in lines:
            if not valid_pattern.match(line):
                return await interaction.response.send_message(
                    t("ERR_INVALID_OFFSET_FORMAT", guild_id=self.wizard_view.guild_id),
                    ephemeral=True
                )
        
        self.wizard_view.data["reminder_offsets"] = lines[: database.MAX_EVENT_REMINDERS]
        self.wizard_view.data["reminder_offset"] = lines[0] if lines else ""
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class CreatorModal(ui.Modal):
    """Modal for changing the displayed event creator ID."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_EVENT_CREATOR", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        self.inp = ui.TextInput(
            label=t("LBL_WIZ_CREATOR_FIELD", guild_id=wizard_view.guild_id),
            default=str(wizard_view.data.get("creator_id") or wizard_view.creator_id),
            required=False
        )
        self.add_item(self.inp)

    async def on_submit(self, interaction: discord.Interaction):
        val = str(self.inp.value).strip()
        self.wizard_view.data["creator_id"] = val if val else None
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class ColorModal(ui.Modal):
    """Modal for setting a custom embed color hex code."""
    
    def __init__(self, wizard_view, current_color: str):
        super().__init__(title=t("MODAL_EVENT_COLOR", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        self.inp = ui.TextInput(
            label=t("LBL_WIZ_COLOR", guild_id=wizard_view.guild_id),
            default=current_color,
            required=True
        )
        self.add_item(self.inp)

    async def on_submit(self, interaction: discord.Interaction):
        self.wizard_view.data["color"] = str(self.inp.value)
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)
