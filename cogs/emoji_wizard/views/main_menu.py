import json
import discord
from discord import ui
import database
from utils.auth import is_admin
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import resolve_placeholders, make_button, make_select_option
from .template_choice import TemplateChoiceView
from .confirm_delete import ConfirmDeleteView
from .help import send_emoji_help
from ..modals.edit_set import EditEmojiSetModal

class EmojiWizardView(ui.LayoutView):
    """Main management console for emoji and role sets (Guild or Global)."""
    
    def __init__(self, bot, guild_id: int, selected_set_id: str = None, is_global: bool = False):
        super().__init__(timeout=600)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_set_id = selected_set_id
        self.is_global = is_global

    async def prepare(self):
        pass

    async def refresh_message(self, interaction: discord.Interaction, status_msg: str = None):
        desc = t("EMOJI_WIZ_INIT_DESC", guild_id=self.guild_id)
        if self.is_global:
            desc = t("LBL_GLOBAL_EMOJI_DESC", guild_id=self.guild_id)

        selection_details = ""
        current = None
        if self.selected_set_id:
            if self.is_global:
                sets = await database.get_all_global_emoji_sets()
            else:
                sets = await database.get_emoji_sets(self.guild_id)
            
            current = next((s for s in sets if s["set_id"] == self.selected_set_id), None)
            if current:
                s_data = current["data"]
                sdata = json.loads(s_data) if isinstance(s_data, str) else s_data
                opts = sdata.get("options", [])
                preview = resolve_placeholders(" ".join([f"{o.get('emoji')} `{o.get('label')}`" for o in opts]))
                selection_details = t("EMOJI_WIZ_SELECTED_DESC", guild_id=self.guild_id, name=current['name'], preview=preview)

        # Create a fresh view instance to ensure clean interaction handling
        new_view = EmojiWizardView(self.bot, self.guild_id, selected_set_id=self.selected_set_id, is_global=self.is_global)
        new_view.clear_items()
        
        # 1. Select Menu
        options = []
        if self.is_global:
            sets = await database.get_all_global_emoji_sets()
        else:
            sets = await database.get_emoji_sets(self.guild_id)
            
        for s in sets:
            s_data = s["data"]
            sdata = json.loads(s_data) if isinstance(s_data, str) else s_data
            label = s["name"][:100]
            
            options.append(make_select_option(
                label=label, 
                value=s["set_id"], 
                default=(s["set_id"] == new_view.selected_set_id)
            ))
        if not options:
            options.append(make_select_option(label=t("LBL_NO_SETS", guild_id=self.guild_id), value="none"))

        set_select = ui.Select(placeholder=t("SEL_EMOJI_SET", guild_id=self.guild_id), options=options)
        async def select_callback(it: discord.Interaction):
            if set_select.values[0] == "none":
                return await it.response.defer()
            new_view.selected_set_id = set_select.values[0]
            await new_view.refresh_message(it)
        set_select.callback = select_callback
        
        row_select = ui.ActionRow(set_select)
        
        # 2. Buttons
        add_btn = make_button(label=t("BTN_NEW_SET", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def add_cb(it: discord.Interaction):
            try:
                log.debug(f"[EmojiWizard] Interaction 'New set' triggered. is_global: {new_view.is_global}, guild_id: {new_view.guild_id}, user: {it.user.id}")
                
                if not new_view.is_global and not await is_admin(it):
                    log.warning(f"[EmojiWizard] Non-admin tried to create new set in guild {new_view.guild_id}")
                    return await it.response.send_message(t("ERR_ADMIN_ONLY", guild_id=new_view.guild_id), ephemeral=True)
                
                if new_view.is_global:
                    is_owner = await new_view.bot.is_owner(it.user)
                    log.debug(f"[EmojiWizard] Global check - User {it.user.id} is_owner: {is_owner}")
                    if not is_owner:
                        log.warning(f"[EmojiWizard] Non-owner tried to create global set: {it.user.id}")
                        return await it.response.send_message(t("ERR_OWNER_ONLY"), ephemeral=True)
                
                view = TemplateChoiceView(new_view)
                await it.response.send_message(view=view, ephemeral=True)
                log.info(f"[EmojiWizard] TemplateChoiceView sent for new set creation.")
            except Exception as e:
                log.error(f"[EmojiWizard] CRITICAL ERROR in add_cb: {e}", exc_info=True)
                if not it.response.is_done():
                    await it.response.send_message(t('ERR_WIZARD_GENERAL', guild_id=new_view.guild_id).replace('{e}', str(e)), ephemeral=True)
                else:
                    await it.followup.send(t('ERR_WIZARD_GENERAL', guild_id=new_view.guild_id).replace('{e}', str(e)), ephemeral=True)
        add_btn.callback = add_cb
        
        clone_btn = make_button(label=t("BTN_CLONE", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def clone_cb(it: discord.Interaction):
            if not new_view.selected_set_id:
                return await it.response.send_message(t("ERR_SELECT_KEY_FIRST", guild_id=new_view.guild_id), ephemeral=True)
            cur_sets = await database.get_all_global_emoji_sets() if new_view.is_global else await database.get_emoji_sets(new_view.guild_id)
            curr = next((s for s in cur_sets if s["set_id"] == new_view.selected_set_id), None)
            if not curr:
                return await it.response.send_message(t("ERR_NO_SET_FOUND", guild_id=new_view.guild_id), ephemeral=True)
            modal = EditEmojiSetModal(new_view, curr)
            modal.title = t("MODAL_EMOJI_SET_CLONE", guild_id=new_view.guild_id)
            modal.is_clone = True
            await it.response.send_modal(modal)
        clone_btn.callback = clone_cb
        
        edit_btn = make_button(label=t("BTN_EDIT", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def edit_cb(it: discord.Interaction):
            if not new_view.selected_set_id:
                return await it.response.send_message(t("ERR_SELECT_KEY_FIRST", guild_id=new_view.guild_id), ephemeral=True)
            cur_sets = await database.get_all_global_emoji_sets() if new_view.is_global else await database.get_emoji_sets(new_view.guild_id)
            curr = next((s for s in cur_sets if s["set_id"] == new_view.selected_set_id), None)
            if not curr:
                return await it.response.send_message(t("ERR_NO_SET_FOUND", guild_id=new_view.guild_id), ephemeral=True)
            await it.response.send_modal(EditEmojiSetModal(new_view, curr))
        edit_btn.callback = edit_cb
        
        del_btn = make_button(label=t("BTN_DELETE", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def del_cb(it: discord.Interaction):
            if not new_view.selected_set_id:
                return await it.response.send_message(t("ERR_SELECT_SET_DELETE", guild_id=new_view.guild_id), ephemeral=True)
            
            cur_sets = await database.get_all_global_emoji_sets() if new_view.is_global else await database.get_emoji_sets(new_view.guild_id)
            curr = next((s for s in cur_sets if s["set_id"] == new_view.selected_set_id), None)
            if not curr:
                return await it.response.send_message(t("ERR_NO_SET_FOUND", guild_id=new_view.guild_id), ephemeral=True)
            
            conf_view = ConfirmDeleteView(new_view, new_view.selected_set_id, curr["name"])
            await conf_view.build()
            await it.response.send_message(view=conf_view, ephemeral=True)
        del_btn.callback = del_cb
        
        help_btn = make_button(label=t("BTN_HELP", guild_id=new_view.guild_id), style=discord.ButtonStyle.secondary)
        async def help_cb(it: discord.Interaction):
            await send_emoji_help(it, new_view.guild_id)
        help_btn.callback = help_cb
        
        row_btns = ui.ActionRow(add_btn, clone_btn, edit_btn, del_btn, help_btn)
        
        container_items = [
            ui.TextDisplay(f"### {t('LBL_GLOBAL_TITLE' if new_view.is_global else 'EMOJI_WIZ_TITLE', guild_id=new_view.guild_id)}"),
            ui.Separator(),
            ui.TextDisplay(f"{status_msg}\n\n{desc}" if status_msg else desc),
        ]
        
        if selection_details:
            container_items.append(ui.Separator())
            container_items.append(ui.TextDisplay(selection_details))
            
        container_items.append(ui.Separator())
        container_items.append(row_select)
        container_items.append(row_btns)
        
        container = ui.Container(*container_items, accent_color=0x40C4FF)
        new_view.add_item(container)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embeds=[], view=new_view)
        elif interaction.type in (discord.InteractionType.component, discord.InteractionType.modal_submit):
            await interaction.response.edit_message(embeds=[], view=new_view)
        else:
            await interaction.response.send_message(view=new_view, ephemeral=True)
