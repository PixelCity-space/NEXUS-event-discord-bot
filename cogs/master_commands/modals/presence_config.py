import json
import uuid
import discord
from discord import ui
import database
from utils.i18n import t

class PresenceConfigModal(ui.Modal):
    """Modal to configure bot presence rotation interval and mode."""
    
    rotate_time = ui.TextInput(label="Time", placeholder="30", default="30")
    rotate_mode = ui.TextInput(label="Mode", placeholder="random", default="random")

    def __init__(self, current_config: dict, refresh_callback):
        super().__init__(title=t("MODAL_PRESENCE_CFG", guild_id=None))
        self.rotate_time.label = t("MASTER_PRESENCE_CFG_TIME", guild_id=None)
        self.rotate_time.placeholder = t("MASTER_PRESENCE_CFG_TIME_PH", guild_id=None)
        self.rotate_mode.label = t("MASTER_PRESENCE_CFG_MODE", guild_id=None)
        self.rotate_mode.placeholder = t("MASTER_PRESENCE_CFG_MODE_PH", guild_id=None)
        
        self.refresh_callback = refresh_callback
        self.rotate_time.default = str(current_config.get("time", 30))
        self.rotate_mode.default = current_config.get("mode", "random")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            time_val = int(self.rotate_time.value)
        except ValueError:
            time_val = 30
        
        mode_val = self.rotate_mode.value.lower()
        if mode_val not in ["random", "sequential"]:
            mode_val = "random"

        db_presence = await database.get_global_setting("bot_presence_list")
        config = json.loads(db_presence) if db_presence else {"statuses": []}
        if isinstance(config, list):
            config = {"statuses": [{"id": str(uuid.uuid4()), "type": "watching", "text": txt} for txt in config]}
        
        config["time"] = time_val
        config["mode"] = mode_val
        
        await database.save_global_setting("bot_presence_list", json.dumps(config))
        await interaction.response.defer()
        await self.refresh_callback(interaction)
