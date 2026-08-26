import json
import uuid
import discord
from discord import ui
import database
from utils.i18n import t

class StatusModal(ui.Modal):
    """Modal to add or edit a specific bot presence status."""
    
    text_input = ui.TextInput(label="Text", placeholder="...", required=True)
    type_input = ui.TextInput(label="Type", placeholder="watching", default="watching", required=False)

    def __init__(self, refresh_callback, status_id: str = None, current_data: dict = None):
        title = t("MODAL_STATUS_EDIT", guild_id=None) if status_id else t("MODAL_STATUS_ADD", guild_id=None)
        super().__init__(title=title)
        
        self.text_input.label = t("MASTER_PRESENCE_TXT_LBL", guild_id=None)
        self.text_input.placeholder = t("MASTER_PRESENCE_TXT_PH", guild_id=None)
        self.type_input.label = t("MASTER_PRESENCE_TYPE_LBL", guild_id=None)
        self.type_input.placeholder = t("MASTER_PRESENCE_TYPE_PH", guild_id=None)
        
        self.refresh_callback = refresh_callback
        self.status_id = status_id
        
        if current_data:
            self.text_input.default = current_data.get("text", "")
            self.type_input.default = current_data.get("type", "watching")

    async def on_submit(self, interaction: discord.Interaction):
        db_presence = await database.get_global_setting("bot_presence_list")
        config = json.loads(db_presence) if db_presence else {"time": 30, "mode": "random", "statuses": []}
        if isinstance(config, list):
            config = {"time": 30, "mode": "random", "statuses": [{"id": str(uuid.uuid4()), "type": "watching", "text": t_val} for t_val in config]}
        
        text_val = self.text_input.value.strip()
        type_val = self.type_input.value.lower().strip()
        if type_val not in ["playing", "watching", "listening", "competing"]:
            type_val = "watching"
            
        if self.status_id:
            for s in config["statuses"]:
                if s["id"] == self.status_id:
                    s["text"] = text_val
                    s["type"] = type_val
                    break
        else:
            config["statuses"].append({"id": str(uuid.uuid4()), "type": type_val, "text": text_val})
            
        await database.save_global_setting("bot_presence_list", json.dumps(config))
        await interaction.response.defer()
        await self.refresh_callback(interaction)
