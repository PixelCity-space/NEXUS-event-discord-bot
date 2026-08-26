import json
import discord
from discord import ui
import database
from utils.emojis import ERROR
from utils.i18n import t
from utils.emoji_utils import slugify, parse_emoji_config

class EditEmojiSetModal(ui.Modal):
    """Modal to create, clone, or edit custom emoji sets."""
    
    def __init__(self, wizard_view, set_record: dict):
        super().__init__(title=t("MODAL_EMOJI_SET_EDIT", guild_id=wizard_view.guild_id))
        self.wizard_view = wizard_view
        self.set_id = set_record["set_id"]
        self.is_clone = False
        self.is_new = False
        
        s_data = set_record["data"]
        sdata = json.loads(s_data) if isinstance(s_data, str) else s_data
        opts = sdata.get("options", [])
        row_limit = sdata.get("buttons_per_row", 5)
        
        color_rev = {"success": "G", "danger": "R", "primary": "B", "secondary": "Y"}
        lines = []
        for o in opts:
            limit = o.get("max_slots", 0)
            flags = ""
            if o.get("show_in_list", True):
                flags += "S"
            if o.get("positive", False):
                flags += "P"
            
            style = o.get("button_style", "both")
            if style == "both":
                flags += "B"
            elif style == "emoji":
                flags += "E"
            elif style == "label":
                flags += "T"
            
            col = color_rev.get(o.get("button_color"), "")
            flags += col
            lines.append(f"{o.get('emoji')} | {o.get('label', '')} | {o.get('list_label', '')} | {limit} | {flags}")
        
        opt_text = "\n".join(lines)
        show_mgmt_val = t("LBL_YES", guild_id=wizard_view.guild_id) if sdata.get("show_mgmt", True) else t("LBL_NO", guild_id=wizard_view.guild_id)
        
        self.name_input = ui.TextInput(
            label=t("LBL_SET_NAME", guild_id=wizard_view.guild_id), 
            default=set_record["name"], 
            required=True
        )
        self.opts_input = ui.TextInput(
            label=t("LBL_EDIT_OPTIONS", guild_id=wizard_view.guild_id), 
            placeholder=t("PH_EDIT_OPTIONS", guild_id=wizard_view.guild_id), 
            style=discord.TextStyle.paragraph, 
            default=opt_text, 
            required=True
        )
        self.row_limit = ui.TextInput(
            label=t("LBL_ROW_LIMIT", guild_id=wizard_view.guild_id), 
            default=str(row_limit), 
            required=True
        )
        self.mgmt_input = ui.TextInput(
            label=t("LBL_SHOW_MGMT", guild_id=wizard_view.guild_id), 
            default=show_mgmt_val, 
            placeholder=t("PH_SHOW_MGMT", guild_id=wizard_view.guild_id), 
            required=True
        )
        
        self.add_item(self.name_input)
        self.add_item(self.opts_input)
        self.add_item(self.row_limit)
        self.add_item(self.mgmt_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            row_l = int(self.row_limit.value)
            if not (1 <= row_l <= 5):
                raise ValueError("row limit out of range")
        except (ValueError, TypeError):
            return await interaction.response.send_message(t("ERR_ROW_LIMIT", guild_id=self.wizard_view.guild_id), ephemeral=True)

        show_m = (self.mgmt_input.value.strip().lower() in [t("LBL_YES", guild_id=self.wizard_view.guild_id).lower(), "yes", "igen", "y", "i"])

        try:
            new_opts, p_count = parse_emoji_config(self.opts_input.value)
        except Exception as e:
            return await interaction.response.send_message(f"{ERROR} {e}", ephemeral=True)

        new_data = {
            "options": new_opts,
            "positive_count": p_count,
            "buttons_per_row": row_l,
            "show_mgmt": show_m
        }

        tid = self.set_id
        if self.is_clone or self.is_new:
            tid = slugify(self.name_input.value) or "custom_set"
            if self.wizard_view.is_global:
                existing = await database.get_all_global_emoji_sets()
            else:
                existing = await database.get_emoji_sets(self.wizard_view.guild_id)
            
            existing_ids = [s["set_id"] for s in existing]
            base_id = tid
            counter = 2
            while tid in existing_ids:
                tid = f"{base_id}_{counter}"
                counter += 1
        
        if self.wizard_view.is_global:
            await database.save_global_emoji_set(tid, self.name_input.value, new_data)
            from cogs.event_ui import load_custom_sets
            await load_custom_sets()
            msg = t("MSG_GLOBAL_SAVED", guild_id=self.wizard_view.guild_id)
        else:
            await database.save_emoji_set(self.wizard_view.guild_id, tid, self.name_input.value, new_data)
            msg = t("MSG_ADVANCED_SAVED", guild_id=self.wizard_view.guild_id)

        self.wizard_view.selected_set_id = tid
        await self.wizard_view.refresh_message(interaction, status_msg=msg)
