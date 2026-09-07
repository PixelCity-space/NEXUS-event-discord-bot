import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_select_option, make_button
from ..base_view import BaseSetupView
from ..config_schema import ServerSettings
from ..ui_builder import (
    create_setting_modal_button,
    create_setting_toggle_button,
    create_setting_select,
)

from .registry import register_view

@register_view("event_defaults")
class EventDefaultsView(BaseSetupView):
    """Event default settings configuration view."""

    async def prepare(self, interaction: discord.Interaction):
        """Asynchronously build UI components and bind callbacks."""
        self.clear_items()

        # 1. Modal Config Buttons
        channel_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.DEFAULT_EVENT_CHANNEL,
            label=t("BTN_DEFAULT_CHANNEL", guild_id=self.guild_id),
            modal_label=t("LBL_SET_CHANNEL", guild_id=self.guild_id),
            placeholder=t("PH_CHANNEL_REF", guild_id=self.guild_id),
        )

        max_acc_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.DEFAULT_MAX_PARTICIPANTS,
            label=t("BTN_DEFAULT_MAX_ACC", guild_id=self.guild_id),
            modal_label=t("LBL_SET_MAX_ACC", guild_id=self.guild_id),
            placeholder=t("PH_NUMBER_ZERO", guild_id=self.guild_id),
        )

        repost_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.DEFAULT_REPOST_OFFSET,
            label=t("BTN_DEFAULT_REPOST", guild_id=self.guild_id),
            modal_label=t("SETTING_REPOST_OFFSET", guild_id=self.guild_id),
            placeholder=t("PH_DURATION", guild_id=self.guild_id),
        )

        archive_val = await database.get_guild_setting(
            self.guild_id, ServerSettings.AUTO_ARCHIVE_HOURS.key, default=ServerSettings.AUTO_ARCHIVE_HOURS.default
        )
        archive_btn = create_setting_modal_button(
            parent_view=self,
            setting=ServerSettings.AUTO_ARCHIVE_HOURS,
            label=t("LBL_AUTO_ARCHIVE", guild_id=self.guild_id, val=f"{archive_val}h"),
            modal_label=t("LBL_SET_ARCHIVE_TIME", guild_id=self.guild_id),
            placeholder=t("PH_DEFAULT_ARCHIVE_HOURS", guild_id=self.guild_id),
        )

        back_btn = make_button(label=t("BTN_BACK", guild_id=self.guild_id), style=discord.ButtonStyle.secondary)
        async def back_cb(it: discord.Interaction):
            await self.navigate_to("main", it)
        back_btn.callback = back_cb

        # 2. Toggle Buttons
        wait_val = await database.get_guild_setting(
            self.guild_id, ServerSettings.DEFAULT_USE_WAITING_LIST.key, default=ServerSettings.DEFAULT_USE_WAITING_LIST.default
        )
        async def check_waitlist(is_on: bool, it: discord.Interaction) -> bool:
            if not is_on:
                max_participants = await database.get_guild_setting(
                    self.guild_id, ServerSettings.DEFAULT_MAX_PARTICIPANTS.key, default=ServerSettings.DEFAULT_MAX_PARTICIPANTS.default
                )
                if int(max_participants or 0) <= 0:
                    await it.response.send_message(t("ERR_WAITLIST_NO_CAP", guild_id=self.guild_id), ephemeral=True)
                    return False
            return True

        wait_btn = create_setting_toggle_button(
            parent_view=self,
            setting=ServerSettings.DEFAULT_USE_WAITING_LIST,
            current_value=wait_val,
            label_format=t("BTN_DEFAULT_WAITLIST", guild_id=self.guild_id, state="{state}"),
            on_text=t("LBL_WAITLIST_ON", guild_id=self.guild_id),
            off_text=t("LBL_WAITLIST_OFF", guild_id=self.guild_id),
            pre_toggle_check=check_waitlist,
            save_key_label=t("LBL_WAITLIST_LIMIT", guild_id=self.guild_id),
        )

        temp_val = await database.get_guild_setting(
            self.guild_id, ServerSettings.DEFAULT_USE_TEMP_ROLE.key, default=ServerSettings.DEFAULT_USE_TEMP_ROLE.default
        )
        temp_role_btn = create_setting_toggle_button(
            parent_view=self,
            setting=ServerSettings.DEFAULT_USE_TEMP_ROLE,
            current_value=temp_val,
            label_format=t("BTN_DEFAULT_TEMP_ROLE", guild_id=self.guild_id, state="{state}"),
            on_text=t("LBL_TEMP_ROLE_ON", guild_id=self.guild_id),
            off_text=t("LBL_TEMP_ROLE_OFF", guild_id=self.guild_id),
            save_key_label=t("LBL_WIZ_TEMP_ROLE", guild_id=self.guild_id),
        )

        # 3. Select Menus
        cur_trig = await database.get_guild_setting(
            self.guild_id, ServerSettings.DEFAULT_REPOST_TRIGGER.key, default=ServerSettings.DEFAULT_REPOST_TRIGGER.default
        )
        trig_opts = [
            make_select_option(label=t("SEL_TRIG_BEFORE", guild_id=self.guild_id), value="before_start", default=(cur_trig == "before_start")),
            make_select_option(label=t("SEL_TRIG_AFTER_START", guild_id=self.guild_id), value="after_start", default=(cur_trig == "after_start")),
            make_select_option(label=t("SEL_TRIG_AFTER_END", guild_id=self.guild_id), value="after_end", default=(cur_trig == "after_end")),
        ]
        trig_sel = create_setting_select(
            parent_view=self,
            setting=ServerSettings.DEFAULT_REPOST_TRIGGER,
            options=trig_opts,
            placeholder=t("SEL_TRIG_TYPE", guild_id=self.guild_id),
            save_message_key=t("SEL_TRIG_TYPE", guild_id=self.guild_id),
        )

        cur_promo = await database.get_guild_setting(
            self.guild_id, ServerSettings.DEFAULT_NOTIFY_PROMOTION.key, default=ServerSettings.DEFAULT_NOTIFY_PROMOTION.default
        )
        promo_opts = [
            make_select_option(label=t("SEL_NOTIFY_NONE", guild_id=self.guild_id), value="none", default=(cur_promo == "none")),
            make_select_option(label=t("SEL_NOTIFY_CHANNEL", guild_id=self.guild_id), value="channel", default=(cur_promo == "channel")),
            make_select_option(label=t("SEL_NOTIFY_DM", guild_id=self.guild_id), value="dm", default=(cur_promo == "dm")),
            make_select_option(label=t("SEL_NOTIFY_BOTH", guild_id=self.guild_id), value="both", default=(cur_promo == "both")),
        ]
        async def check_promo_waitlist(val: str, it: discord.Interaction):
            if val != "none":
                wait_check = await database.get_guild_setting(
                    self.guild_id, ServerSettings.DEFAULT_USE_WAITING_LIST.key, default=ServerSettings.DEFAULT_USE_WAITING_LIST.default
                )
                if wait_check.lower() != "true":
                    await it.response.send_message(t("ERR_WAITLIST_DISABLED_PROMO", guild_id=self.guild_id), ephemeral=True)

        promo_sel = create_setting_select(
            parent_view=self,
            setting=ServerSettings.DEFAULT_NOTIFY_PROMOTION,
            options=promo_opts,
            placeholder=t("LBL_PROMOTION_NOTIFY", guild_id=self.guild_id),
            save_message_key=t("LBL_PROMOTION_NOTIFY", guild_id=self.guild_id),
            on_change=check_promo_waitlist,
        )

        # 4. Final Layout Assembly
        event_desc = t('SETUP_EVENT_DEFAULTS_DESC', guild_id=self.guild_id)
        main_container = ui.Container(
            ui.TextDisplay(f"### {t('TITLE_EVENT_DEFAULTS', guild_id=self.guild_id)}\n{event_desc}"),
            ui.ActionRow(channel_btn, max_acc_btn, wait_btn, repost_btn, temp_role_btn),
            ui.ActionRow(archive_btn, back_btn),
            ui.ActionRow(trig_sel),
            ui.ActionRow(promo_sel),
            accent_color=0x40C4FF
        )
        self.add_item(main_container)
