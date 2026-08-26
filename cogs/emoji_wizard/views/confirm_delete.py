import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_button

class ConfirmDeleteView(ui.LayoutView):
    """Safety confirmation view for destructive delete operations."""
    
    def __init__(self, wizard_view, set_id: str, set_name: str):
        super().__init__(timeout=180)
        self.wizard_view = wizard_view
        self.set_id = set_id
        self.set_name = set_name

    async def build(self):
        self.clear_items()
        
        async def cancel_cb(it: discord.Interaction):
            await it.response.defer()
            await it.delete_original_response()

        async def confirm_cb(it: discord.Interaction):
            await it.response.defer()
            if self.wizard_view.is_global:
                pool = await database.get_pool()
                await pool.execute("DELETE FROM global_emoji_sets WHERE set_id = $1", self.set_id)
                from cogs.event_ui import load_custom_sets
                await load_custom_sets()
            else:
                await database.delete_emoji_set(self.wizard_view.guild_id, self.set_id)
            
            self.wizard_view.selected_set_id = None
            await self.wizard_view.refresh_message(it, status_msg=t("MSG_SET_DELETED", guild_id=self.wizard_view.guild_id))

        cancel_btn = make_button(label=t("BTN_CANCEL", guild_id=self.wizard_view.guild_id), style=discord.ButtonStyle.secondary)
        confirm_btn = make_button(label=t("BTN_DELETE", guild_id=self.wizard_view.guild_id), style=discord.ButtonStyle.danger)
        
        cancel_btn.callback = cancel_cb
        confirm_btn.callback = confirm_cb
        
        warning_msg = t("MSG_DELETE_CONFIRM", guild_id=self.wizard_view.guild_id).replace("{name}", self.set_name)
        
        container = ui.Container(
            ui.TextDisplay(warning_msg),
            ui.ActionRow(cancel_btn, confirm_btn),
            accent_color=0xff0000
        )
        self.add_item(container)
