import json
import uuid
import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_button, make_select_option
from .presence_edit import PresenceEditView
from ..modals.status import StatusModal
from ..modals.presence_config import PresenceConfigModal

class MasterPresenceView(ui.LayoutView):
    """Visual console for managing the bot's dynamic presence list and intervals."""
    
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.current_config = {"time": 30, "mode": "random", "statuses": []}

    async def load_config(self):
        db_presence = await database.get_global_setting("bot_presence_list")
        if db_presence:
            parsed = json.loads(db_presence)
            if isinstance(parsed, list):
                self.current_config["statuses"] = [{"id": str(uuid.uuid4()), "type": "watching", "text": t_val} for t_val in parsed]
            else:
                self.current_config = parsed
        else:
            self.current_config = {"time": 30, "mode": "random", "statuses": []}

    async def refresh_message(self, interaction: discord.Interaction):
        await self.load_config()
        
        time_cfg = self.current_config.get("time", 30)
        mode_cfg = self.current_config.get("mode", "random")
        val = t("MASTER_PRESENCE_CFG_VAL", guild_id=None).replace("{time}", str(time_cfg)).replace("{mode}", mode_cfg.capitalize())
        
        statuses = self.current_config.get("statuses", [])
        if statuses:
            lines = []
            for i, s in enumerate(statuses):
                type_key = f"PRESENCE_TYPE_{s.get('type', 'watching').upper()}"
                type_text = t(type_key, guild_id=None)
                lines.append(t("MASTER_PRESENCE_LIST_ITEM", guild_id=None, i=i+1, type_text=type_text, text=s.get('text', '')))
            active_val = "\n".join(lines)
        else:
            active_val = t("MASTER_PRESENCE_NONE", guild_id=None)

        self.clear_items()
        
        add_btn = make_button(label=t("BTN_PRESENCE_BTN_ADD", guild_id=None), style=discord.ButtonStyle.secondary)
        async def add_cb(it: discord.Interaction):
            await it.response.send_modal(StatusModal(self.refresh_message))
        add_btn.callback = add_cb
        
        cfg_btn = make_button(label=t("BTN_PRESENCE_BTN_CFG", guild_id=None), style=discord.ButtonStyle.secondary)
        async def cfg_cb(it: discord.Interaction):
            await it.response.send_modal(PresenceConfigModal(self.current_config, self.refresh_message))
        cfg_btn.callback = cfg_cb
        
        row_buttons = ui.ActionRow(add_btn, cfg_btn)

        container_items = [
            ui.TextDisplay(f"### {t('MASTER_PRESENCE_TITLE', guild_id=None)}"),
            ui.Separator(),
            ui.TextDisplay(t("MASTER_PRESENCE_DESC", guild_id=None)),
            ui.Separator(),
            ui.TextDisplay(f"**{t('MASTER_PRESENCE_CFG', guild_id=None)}**\n{val}"),
            ui.Separator(),
            ui.TextDisplay(f"**{t('MASTER_PRESENCE_ACTIVE', guild_id=None)}**\n{active_val}"),
            ui.Separator()
        ]

        if statuses:
            options = []
            for s in statuses:
                type_key = f"PRESENCE_TYPE_{s.get('type', 'watching').upper()}"
                type_text = t(type_key, guild_id=None).replace("**", "")
                label = f"{type_text}: {s.get('text', '')}"[:100]
                options.append(make_select_option(label=label, value=s["id"]))
            
            select = ui.Select(placeholder=t("MASTER_PRESENCE_SEL_PH", guild_id=None), options=options)
            async def select_cb(it: discord.Interaction):
                sel_id = select.values[0]
                sel_data = next((x for x in self.current_config["statuses"] if x["id"] == sel_id), None)
                if sel_data:
                    edit_view = PresenceEditView(self, sel_id, sel_data)
                    await edit_view.refresh_message(it)
            select.callback = select_cb
            
            row_select = ui.ActionRow(select)
            container_items.append(row_select)

        container_items.append(row_buttons)
        container = ui.Container(*container_items, accent_color=0x40C4FF)
        self.add_item(container)
            
        if interaction.response.is_done():
            await interaction.edit_original_response(embeds=[], view=self)
        elif interaction.type == discord.InteractionType.component:
            await interaction.response.edit_message(embeds=[], view=self)
        else:
            await interaction.response.send_message(view=self, ephemeral=True)
