import discord
from discord import ui
import database
from utils.emojis import GLOBE
from utils.i18n import t
from utils.emoji_utils import to_emoji, make_button
from ..base_view import BaseSetupView
from ..config_schema import ServerSettings
from ..ui_builder import (
    create_setting_modal_button,
    create_color_dropdown,
)

class ServerSetupView(BaseSetupView):
    """Visual console for guild settings and defaults using Components V2."""

    async def prepare(self, interaction: discord.Interaction):
        """Asynchronously build UI components and bind callbacks."""
        self.clear_items()
        
        # Deferred import to prevent circular dependencies
        from .general import GeneralSetupView
        from .reminders import ReminderSetupView
        from .event_defaults import EventDefaultsView

        # 1. Navigation Action Buttons
        general_btn = make_button(
            label=t("BTN_GENERAL", guild_id=self.guild_id), 
            style=discord.ButtonStyle.secondary
        )
        async def general_cb(it: discord.Interaction):
            await self.navigate_to(GeneralSetupView, it)
        general_btn.callback = general_cb

        reminder_btn = make_button(
            label=t("BTN_REMINDERS", guild_id=self.guild_id), 
            style=discord.ButtonStyle.secondary
        )
        async def reminder_cb(it: discord.Interaction):
            await self.navigate_to(ReminderSetupView, it)
        reminder_btn.callback = reminder_cb

        defaults_btn = make_button(
            label=t("BTN_EVENT_DEFAULTS", guild_id=self.guild_id), 
            style=discord.ButtonStyle.secondary
        )
        async def defaults_cb(it: discord.Interaction):
            await self.navigate_to(EventDefaultsView, it)
        defaults_btn.callback = defaults_cb

        # 2. Timezone Modal Button
        curr_tz = await database.get_guild_setting(
            self.guild_id, ServerSettings.TIMEZONE.key, default=ServerSettings.TIMEZONE.default
        )
        local_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.TIMEZONE,
            label=curr_tz,
            modal_label=t("SETTING_TIMEZONE", guild_id=self.guild_id),
            placeholder=t("PH_TIMEZONE", guild_id=self.guild_id),
            emoji=to_emoji(GLOBE),
            style=discord.ButtonStyle.secondary,
        )

        # 3. Color Dropdown Selection
        cur_color_raw = await database.get_guild_setting(
            self.guild_id, ServerSettings.DEFAULT_COLOR.key, default=ServerSettings.DEFAULT_COLOR.default
        )
        color_sel = create_color_dropdown(
            parent_view=self,
            current_color_raw=cur_color_raw,
            setting=ServerSettings.DEFAULT_COLOR,
            placeholder=t("SEL_COLOR", guild_id=self.guild_id),
            modal_label=t("SETTING_COLOR", guild_id=self.guild_id),
            modal_placeholder=t("PH_COLOR", guild_id=self.guild_id),
        )

        # 4. Final Layout Assembly
        main_container = ui.Container(
            ui.TextDisplay(f"### {t('SETUP_MAIN_TITLE', guild_id=self.guild_id)}\n{t('SETUP_MAIN_DESC', guild_id=self.guild_id)}"),
            ui.ActionRow(general_btn, local_btn, reminder_btn, defaults_btn),
            ui.Separator(),
            ui.TextDisplay(t('LBL_SET_COLOR_DESC', guild_id=self.guild_id)),
            ui.ActionRow(color_sel),
            accent_color=0x40C4FF
        )
        self.add_item(main_container)
