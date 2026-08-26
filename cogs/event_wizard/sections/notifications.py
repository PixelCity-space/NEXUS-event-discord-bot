import discord
from discord import ui
from utils.i18n import t
from utils.emoji_utils import make_select_option, make_button
from ..modals import (
    ReminderOffsetModal,
    ReminderMessagesModal,
)

def build_notifications_section(view) -> list[ui.Item]:
    """Builds the reminder and notification configuration accordion."""
    if not view.show_reminder:
        return []

    items: list[ui.Item] = []

    if view.wizard_type == "lobby":
        cur_rem_type = view.data.get("reminder_type", "none")
        rem_type_opts = [
            make_select_option(label=t("SEL_REM_NONE", guild_id=view.guild_id), value="none", default=(cur_rem_type == "none")),
            make_select_option(label=t("SEL_REM_DM", guild_id=view.guild_id), value="dm", default=(cur_rem_type == "dm")),
            make_select_option(label=t("SEL_REM_PING", guild_id=view.guild_id), value="ping", default=(cur_rem_type == "ping")),
            make_select_option(label=t("SEL_REM_BOTH", guild_id=view.guild_id), value="both", default=(cur_rem_type == "both"))
        ]
        rem_type_sel = ui.Select(placeholder=t("SEL_LOBBY_FILL_NOTIFY", guild_id=view.guild_id), options=rem_type_opts)
        async def rem_type_cb(it: discord.Interaction):
            await it.response.defer()
            view.data["reminder_type"] = rem_type_sel.values[0]
            await view.save_to_draft()
            await view.refresh_message(it)
        rem_type_sel.callback = rem_type_cb

        items.append(ui.Separator())
        items.append(ui.TextDisplay(t("MSG_LOBBY_REMINDER_HINT", guild_id=view.guild_id)))
        items.append(ui.TextDisplay(t("LBL_CHOOSE_LOBBY_NOTIFY", guild_id=view.guild_id)))
        items.append(ui.ActionRow(rem_type_sel))
    else:
        ro_list = view.data.get("reminder_offsets") or []
        if not isinstance(ro_list, list):
            ro_list = []
        off_preview = ", ".join(ro_list) if ro_list else str(view.data.get("reminder_offset") or "—")
        if len(off_preview) > 500:
            off_preview = off_preview[:497] + "..."

        items.append(ui.Separator())
        items.append(ui.TextDisplay(t("LBL_REMINDER_LIST_PREVIEW", guild_id=view.guild_id, offsets=off_preview)))

        # Reminder Offset Button
        rem_offset_btn = make_button(label=t("BTN_REMINDER_OFFSET", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
        async def rem_offset_cb(it: discord.Interaction):
            await it.response.send_modal(ReminderOffsetModal(view))
        rem_offset_btn.callback = rem_offset_cb

        # Reminder Messages Button
        has_reminders = len(ro_list) > 0
        rem_msg_btn = make_button(
            label=t("BTN_REMINDER_MESSAGES", guild_id=view.guild_id),
            style=discord.ButtonStyle.gray,
            disabled=not has_reminders
        )
        async def rem_msg_cb(it: discord.Interaction):
            await it.response.send_modal(ReminderMessagesModal(view))
        rem_msg_btn.callback = rem_msg_cb

        items.append(ui.ActionRow(rem_offset_btn, rem_msg_btn))

    return items
