import discord
from discord import ui
import database
from utils.i18n import t, load_guild_translations
from utils.emoji_utils import make_select_option, make_button
from ..base_view import BaseSetupView
from ..config_schema import ServerSettings
from ..ui_builder import (
    create_setting_modal_button,
    create_setting_select,
)

from .registry import register_view

@register_view("general")
class GeneralSetupView(BaseSetupView):
    """General setup view for bot language, template language, and admin permissions."""

    async def prepare(self, interaction: discord.Interaction):
        """Asynchronously build UI components and bind callbacks."""
        self.clear_items()

        # 1. Admin Roles & Channels Modal Buttons
        roles_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.ADMIN_ROLE_IDS,
            label=t("BTN_ADMIN_ROLES", guild_id=self.guild_id),
            modal_label=t("SETTING_ADMIN_ROLES", guild_id=self.guild_id),
            placeholder=t("PH_ID_LIST", guild_id=self.guild_id),
            is_long=True,
        )

        channels_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.ADMIN_CHANNEL_IDS,
            label=t("BTN_ADMIN_CHANNELS", guild_id=self.guild_id),
            modal_label=t("SETTING_ADMIN_CHANNELS", guild_id=self.guild_id),
            placeholder=t("PH_ID_LIST", guild_id=self.guild_id),
            is_long=True,
        )

        back_btn = make_button(label=t("BTN_BACK", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def back_cb(it: discord.Interaction):
            await self.navigate_to("main", it)
        back_btn.callback = back_cb

        # 2. Bot Language Select
        cur_lang = await database.get_guild_setting(
            self.guild_id, ServerSettings.LANGUAGE.key, default=ServerSettings.LANGUAGE.default
        )
        lang_opts = [
            make_select_option(label=t("LBL_LANG_HU", guild_id=self.guild_id), value="hu", default=(cur_lang == "hu")),
            make_select_option(label=t("LBL_LANG_EN", guild_id=self.guild_id), value="en", default=(cur_lang == "en")),
        ]
        async def on_lang_change(val: str, it: discord.Interaction):
            await load_guild_translations(self.guild_id)

        lang_sel = create_setting_select(
            parent_view=self,
            setting=ServerSettings.LANGUAGE,
            options=lang_opts,
            placeholder=t("SEL_BOT_LANG", guild_id=self.guild_id),
            save_message_key="Language",
            on_change=on_lang_change,
        )

        # 3. Template Language Select
        cur_tpl_lang = await database.get_guild_setting(
            self.guild_id, ServerSettings.TEMPLATE_LANGUAGE.key, default=ServerSettings.TEMPLATE_LANGUAGE.default
        )
        tpl_opts = [
            make_select_option(label=t("SEL_LANG_DEFAULT", guild_id=self.guild_id), value="default", default=(cur_tpl_lang == "default")),
            make_select_option(label=t("LBL_LANG_HU", guild_id=self.guild_id), value="hu", default=(cur_tpl_lang == "hu")),
            make_select_option(label=t("LBL_LANG_EN", guild_id=self.guild_id), value="en", default=(cur_tpl_lang == "en")),
        ]
        tpl_sel = create_setting_select(
            parent_view=self,
            setting=ServerSettings.TEMPLATE_LANGUAGE,
            options=tpl_opts,
            placeholder=t("LBL_TEMPLATE_LANG", guild_id=self.guild_id),
            save_message_key=t("LBL_TEMPLATE_LANG", guild_id=self.guild_id),
            on_change=on_lang_change,
        )

        # 4. Final Layout Assembly
        main_container = ui.Container(
            ui.TextDisplay(f"### {t('SETUP_GENERAL_TITLE', guild_id=self.guild_id)}\n{t('SETUP_GENERAL_DESC', guild_id=self.guild_id)}"),
            ui.ActionRow(roles_btn, channels_btn, back_btn),
            ui.Separator(),
            ui.TextDisplay(t('LBL_SET_BOT_LANG_DESC', guild_id=self.guild_id)),
            ui.ActionRow(lang_sel),
            ui.ActionRow(tpl_sel),
            accent_color=0x40C4FF
        )
        self.add_item(main_container)
