import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_select_option, make_button
from ..base_view import BaseSetupView
from ..config_schema import ServerSettings
from ..modals import MultiReminderOffsetModal
from ..ui_builder import create_setting_select

class ReminderSetupView(BaseSetupView):
    """Reminder and status notification configuration view."""

    async def prepare(self, interaction: discord.Interaction):
        """Asynchronously build UI components and bind callbacks."""
        self.clear_items()
        
        from .main_menu import ServerSetupView

        # 1. Back Button
        back_btn = make_button(label=t("BTN_BACK", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def back_cb(it: discord.Interaction):
            await self.navigate_to(ServerSetupView, it)
        back_btn.callback = back_cb

        # 2. Reminder Offset Button
        offset_btn = make_button(label=t("BTN_REMINDER_OFFSET", guild_id=self.guild_id), style=discord.ButtonStyle.gray)
        async def offset_cb(it: discord.Interaction):
            curr = await database.get_guild_setting(
                self.guild_id, ServerSettings.DEFAULT_REMINDER_OFFSET.key, default=ServerSettings.DEFAULT_REMINDER_OFFSET.default
            )
            modal = MultiReminderOffsetModal(self.guild_id, curr, self)
            await it.response.send_modal(modal)
        offset_btn.callback = offset_cb
        
        # 3. Status Notification Type Dropdown
        cur_status_notify = await database.get_guild_setting(
            self.guild_id, ServerSettings.STATUS_NOTIFICATION_TYPE.key, default=ServerSettings.STATUS_NOTIFICATION_TYPE.default
        )
        status_opts = [
            make_select_option(label=t("OPT_NOTIFY_NONE", guild_id=self.guild_id) or "None", value="none", default=(cur_status_notify == "none")),
            make_select_option(label=t("OPT_NOTIFY_DM", guild_id=self.guild_id) or "DM Only", value="dm", default=(cur_status_notify == "dm")),
            make_select_option(label=t("OPT_NOTIFY_CHAT", guild_id=self.guild_id) or "Ping in Channel Only", value="chat", default=(cur_status_notify == "chat")),
            make_select_option(label=t("OPT_NOTIFY_BOTH", guild_id=self.guild_id) or "Both", value="both", default=(cur_status_notify == "both")),
        ]
        status_sel = create_setting_select(
            parent_view=self,
            setting=ServerSettings.STATUS_NOTIFICATION_TYPE,
            options=status_opts,
            placeholder=t("PH_STATUS_NOTIFY", guild_id=self.guild_id) or "Select status notification mode...",
            save_message_key=t("LBL_PROMOTION_NOTIFY", guild_id=self.guild_id),
        )

        # 4. Final Layout Assembly
        main_container = ui.Container(
            ui.TextDisplay(f"### {t('TITLE_SETUP_REMINDERS', guild_id=self.guild_id)}\n{t('SETUP_REMINDERS_DESC', guild_id=self.guild_id)}"),
            ui.ActionRow(offset_btn, back_btn),
            ui.Separator(),
            ui.TextDisplay(t('LBL_SET_STATUS_NOTIFY_DESC', guild_id=self.guild_id)),
            ui.ActionRow(status_sel),
            accent_color=0x40C4FF
        )
        self.add_item(main_container)
