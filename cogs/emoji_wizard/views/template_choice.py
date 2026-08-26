import json
import discord
from discord import ui
from utils.emojis import ERROR
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import to_emoji, resolve_placeholders, make_select_option
from utils.templates import ICON_SET_TEMPLATES, get_template_data
from ..modals.edit_set import EditEmojiSetModal

class TemplateChoiceView(ui.LayoutView):
    """View to select a base template for creating a new custom emoji set."""
    
    def __init__(self, wizard_view):
        super().__init__(timeout=300)
        self.wizard_view = wizard_view
        log.debug(f"[EmojiWizard] Initializing TemplateChoiceView. Global: {wizard_view.is_global}")
        
        options = []
        for k, v in ICON_SET_TEMPLATES.items():
            label = resolve_placeholders(t(v["label_key"], guild_id=self.wizard_view.guild_id))
            options.append(make_select_option(label=label[:100], value=k, emoji=to_emoji(v["emoji"]) or None))
        
        options.append(make_select_option(label=t("LBL_EMPTY_SET", guild_id=self.wizard_view.guild_id), value="empty"))
        
        select_template = ui.Select(placeholder=t("SEL_TEMPLATE", guild_id=self.wizard_view.guild_id), options=options)
        async def select_callback(interaction: discord.Interaction):
            try:
                template = select_template.values[0]
                log.debug(f"[EmojiWizard] Template selected: {template}")
                
                initial_text = ICON_SET_TEMPLATES.get(template, {}).get("text", "") if template != "empty" else ""
                tmpl_data = get_template_data(template) if template != "empty" else {"options": [], "buttons_per_row": 5, "show_mgmt": False}
                dummy_record = {
                    "set_id": "", 
                    "name": "",
                    "data": json.dumps(tmpl_data)
                }
                edit_modal = EditEmojiSetModal(self.wizard_view, dummy_record)
                edit_modal.title = t("MODAL_EMOJI_SET_NEW", guild_id=self.wizard_view.guild_id)
                edit_modal.opts_input.default = initial_text
                edit_modal.is_new = True 
                await interaction.response.send_modal(edit_modal)
                log.info(f"[EmojiWizard] EditEmojiSetModal sent for template: {template}")
            except Exception as e:
                log.error(f"[EmojiWizard] Error in TemplateChoiceView select_callback: {e}", exc_info=True)
                await interaction.response.send_message(f"{ERROR} {e}", ephemeral=True)
        select_template.callback = select_callback

        container = ui.Container(
            ui.TextDisplay(f"### {t('LBL_CHOOSE_TEMPLATE', guild_id=self.wizard_view.guild_id)}"),
            ui.Separator(),
            ui.ActionRow(select_template),
            accent_color=0x40C4FF
        )
        self.add_item(container)
