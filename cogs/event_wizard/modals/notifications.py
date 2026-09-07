import discord
from discord import ui
from utils.i18n import t
from utils.extra_data import parse_extra_data

class NotificationSettingsModal(ui.Modal):
    """Modal for configuring custom promotion messages upon promotion from waiting list."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_NOTIFICATION_SETTINGS", guild_id=wizard_view.guild_id)[:45])
        self.wizard_view = wizard_view
        
        extra_dto = parse_extra_data(wizard_view.data.get("extra_data"))
        self.promo_input = ui.TextInput(
            label=t("LBL_PROMO_MSG", guild_id=wizard_view.guild_id)[:45],
            default=extra_dto.custom_promo_msg or "",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.promo_input)

    async def on_submit(self, interaction: discord.Interaction):
        extra_dto = parse_extra_data(self.wizard_view.data.get("extra_data"))
        extra_dto.custom_promo_msg = self.promo_input.value
        self.wizard_view.data["extra_data"] = extra_dto.to_json()
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)

class ReminderMessagesModal(ui.Modal):
    """Modal for defining custom messages for each configured reminder offset."""
    
    def __init__(self, wizard_view):
        super().__init__(title=t("MODAL_REMINDER_MESSAGES", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        gid = wizard_view.guild_id
        data = wizard_view.data
        
        offsets = data.get("reminder_offsets") or []
        msgs = data.get("reminder_messages") or []
        
        display_offsets = offsets if offsets else []
        
        self.inputs = []
        for i in range(len(display_offsets)):
            off_full = display_offsets[i]
            label = t("LBL_REMINDER_MSG_N", guild_id=gid, n=i+1, offset=off_full)
            default_val = msgs[i] if i < len(msgs) else ""
            
            inp = ui.TextInput(
                label=label[:45],
                style=discord.TextStyle.paragraph,
                default=str(default_val or ""),
                required=False,
                max_length=400
            )
            self.inputs.append(inp)
            self.add_item(inp)

    async def on_submit(self, interaction: discord.Interaction):
        msgs = [inp.value.strip() for inp in self.inputs]
        self.wizard_view.data["reminder_messages"] = msgs
        await self.wizard_view.save_to_draft()
        await self.wizard_view.refresh_message(interaction)
