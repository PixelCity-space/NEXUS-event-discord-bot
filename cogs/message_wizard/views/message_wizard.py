from typing import Optional
import discord
from discord import ui
import database
from utils.emojis import SHIELD, PREVIEW, IDEA, INDICATOR
from utils.emoji_utils import make_button, make_select_option
from utils.i18n import t, load_guild_translations, CATEGORIES
from utils.auth import is_admin
from utils.logger import log
from ..modals.message_edit import MessageEditModal

class MessageWizardView(ui.LayoutView):
    """Admin interactive UI to manage and override server message translations."""
    
    def __init__(self, bot: discord.Client, guild_id: int | str, selected_key: Optional[str] = None):
        super().__init__(timeout=600)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_category: str = "Notifications"
        self.selected_key = selected_key

    async def prepare(self, interaction: discord.Interaction) -> None:
        """Build UI components, select options, and action buttons."""
        await load_guild_translations(self.guild_id)
        self.clear_items()
        
        desc = t("MSG_WIZ_DESC", guild_id=self.guild_id)
        
        if self.selected_key:
            friendly_name = t(f"KEY_{self.selected_key}", guild_id=self.guild_id)
            if friendly_name == f"KEY_{self.selected_key}":
                friendly_name = self.selected_key
            
            current_val = t(self.selected_key, guild_id=self.guild_id)
            preview = current_val.replace("{user_id}", f"<@{interaction.user.id}>")\
                                 .replace("{title}", "Példa Esemény")\
                                 .replace("{role}", "Tank")\
                                 .replace("{emoji}", SHIELD)\
                                 .replace("{status}", "AKTÍV")
            
            desc += f"\n\n**{PREVIEW} {t('LBL_PREVIEW', guild_id=self.guild_id)} ({friendly_name}):**\n> {preview}"
            desc += f"\n\n**{IDEA} {t('LBL_VARIABLES', guild_id=self.guild_id)}:**\n`{{title}}`, `{{user_id}}`, `{{role}}`, `{{emoji}}`, `{{status}}`"

        # 1. Key Select Dropdown
        keys = CATEGORIES.get(self.selected_category, [])
        options = []
        for k in keys:
            friendly_name = t(f"KEY_{k}", guild_id=self.guild_id)
            if friendly_name == f"KEY_{k}":
                friendly_name = k
            
            current_val = t(k, guild_id=self.guild_id)
            is_overridden = (current_val != t(k))
            label = f"{f'{INDICATOR} ' if is_overridden else ''}{friendly_name}"
            options.append(make_select_option(
                label=label[:100], 
                value=k, 
                description=current_val[:100],
                default=(k == self.selected_key)
            ))

        if not options:
            options.append(make_select_option(label=t("ERR_NO_KEYS_AVAILABLE", guild_id=self.guild_id), value="none", disabled=True))
            
        key_select = ui.Select(placeholder=t("SEL_KEY", guild_id=self.guild_id), options=options)
        async def key_callback(it: discord.Interaction):
            if key_select.values[0] == "none":
                return await it.response.defer()
            self.selected_key = key_select.values[0]
            await self.refresh_message(it)
        key_select.callback = key_callback

        row_select = ui.ActionRow(key_select)

        # 2. Buttons
        edit_btn = make_button(label=t("BTN_EDIT", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def edit_cb(it: discord.Interaction):
            try:
                if not await is_admin(it):
                    return await it.response.send_message(t("ERR_ADMIN_ONLY", guild_id=self.guild_id), ephemeral=True)
                if not self.selected_key:
                    return await it.response.send_message(t("ERR_SELECT_KEY_FIRST", guild_id=self.guild_id), ephemeral=True)
                
                current_val = t(self.selected_key, guild_id=self.guild_id)
                await it.response.send_modal(MessageEditModal(self, self.selected_key, current_val, self.guild_id))
            except Exception as e:
                log.error(f"[MessageWizard] Error in edit_cb: {e}", exc_info=True)
        edit_btn.callback = edit_cb

        reset_btn = make_button(label=t("BTN_RESET_DEFAULT", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def reset_cb(it: discord.Interaction):
            if not await is_admin(it):
                return await it.response.send_message(t("ERR_ADMIN_ONLY", guild_id=self.guild_id), ephemeral=True)
            if not self.selected_key:
                return await it.response.send_message(t("ERR_SELECT_KEY_RESET", guild_id=self.guild_id), ephemeral=True)
            
            await database.delete_guild_translation(self.guild_id, self.selected_key)
            await load_guild_translations(self.guild_id)
            await self.refresh_message(it)
        reset_btn.callback = reset_cb

        row_btns = ui.ActionRow(edit_btn, reset_btn)

        # 3. Assemble Container
        container_items = [
            ui.TextDisplay(f"### {t('MSG_WIZ_TITLE', guild_id=self.guild_id)}"),
            ui.Separator(),
            ui.TextDisplay(desc),
            ui.Separator(),
            row_select,
            row_btns
        ]
        
        container = ui.Container(*container_items, accent_color=0x4169E1)
        self.add_item(container)

    async def refresh_message(self, interaction: discord.Interaction) -> None:
        new_view = MessageWizardView(self.bot, self.guild_id, selected_key=self.selected_key)
        await new_view.prepare(interaction)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embeds=[], view=new_view)
        elif interaction.type in (discord.InteractionType.component, discord.InteractionType.modal_submit):
            await interaction.response.edit_message(embeds=[], view=new_view)
        else:
            await interaction.response.send_message(view=new_view, ephemeral=True)
