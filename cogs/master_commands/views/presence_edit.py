import json
import uuid
import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_button
from ..modals.status import StatusModal

class PresenceEditView(ui.LayoutView):
    """View to edit or delete a selected presence status entry."""
    
    def __init__(self, parent_view, status_id: str, status_data: dict):
        super().__init__(timeout=300)
        self.parent_view = parent_view
        self.status_id = status_id
        self.status_data = status_data

    async def refresh_message(self, interaction: discord.Interaction):
        type_key = f"PRESENCE_TYPE_{self.status_data.get('type', 'watching').upper()}"
        type_text = t(type_key, guild_id=None)
        desc = t("MASTER_PRESENCE_EDIT_DESC", guild_id=None).replace("{type}", type_text).replace("{text}", self.status_data.get('text', ''))
        
        self.clear_items()
        edit_btn = make_button(label=t("BTN_PRESENCE_BTN_EDIT", guild_id=None), style=discord.ButtonStyle.secondary)
        async def edit_cb(it: discord.Interaction):
            await it.response.send_modal(StatusModal(self.parent_view.refresh_message, self.status_id, self.status_data))
        edit_btn.callback = edit_cb
        
        del_btn = make_button(label=t("BTN_PRESENCE_BTN_DEL", guild_id=None), style=discord.ButtonStyle.secondary)
        async def del_cb(it: discord.Interaction):
            db_presence = await database.get_global_setting("bot_presence_list")
            if not db_presence:
                config = {"time": 30, "mode": "random", "statuses": []}
            else:
                config = json.loads(db_presence)
                if isinstance(config, list):
                    config = {
                        "time": 30,
                        "mode": "random",
                        "statuses": [
                            {"id": str(uuid.uuid4()), "type": "watching", "text": t_val}
                            for t_val in config
                        ],
                    }
                if not isinstance(config, dict):
                    config = {"time": 30, "mode": "random", "statuses": []}
                statuses = config.get("statuses")
                if not isinstance(statuses, list):
                    statuses = []
                config["statuses"] = [s for s in statuses if s.get("id") != self.status_id]
            await database.save_global_setting("bot_presence_list", json.dumps(config))
            await it.response.defer()
            await self.parent_view.refresh_message(it)
        del_btn.callback = del_cb
        
        back_btn = make_button(label=t("BTN_BACK", guild_id=None), style=discord.ButtonStyle.secondary)
        async def back_cb(it: discord.Interaction):
            await it.response.defer()
            await self.parent_view.refresh_message(it)
        back_btn.callback = back_cb

        row = ui.ActionRow(edit_btn, del_btn, back_btn)
        
        container = ui.Container(
            ui.TextDisplay(f"### {t('MASTER_PRESENCE_EDIT_MODE', guild_id=None)}"),
            ui.Separator(),
            ui.TextDisplay(desc),
            row,
            accent_color=0x40C4FF
        )
        self.add_item(container)
        
        await interaction.response.edit_message(embeds=[], view=self)
