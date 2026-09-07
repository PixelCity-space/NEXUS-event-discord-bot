import discord
from discord import ui
from utils.i18n import t
from utils.emoji_utils import make_select_option, make_button
from utils.extra_data import parse_extra_data
from ..modals import (
    RoleLimitsModal,
    NotificationSettingsModal,
    RsvpRolesModal,
    AdvancedSettingsModal,
    CreatorModal,
    ColorModal,
)

def build_settings_section(view) -> list[ui.Item]:
    """Builds the advanced participation and configuration settings accordion."""
    if not view.show_advanced:
        return []

    items: list[ui.Item] = [
        ui.Separator(),
        ui.TextDisplay(f"**{t('LBL_ADV_CAT_PARTICIPATION', guild_id=view.guild_id)}**"),
    ]

    # Role Limits Button
    async def role_cb(it: discord.Interaction):
        from cogs.event_ui import get_active_set
        active_set = get_active_set(view.data.get("icon_set", "standard"))
        await it.response.send_modal(RoleLimitsModal(view, active_set))
    role_btn = make_button(label=t("BTN_ROLE_LIMITS", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
    role_btn.callback = role_cb

    # Allowed RSVP Roles Button
    async def rsvp_roles_cb(it: discord.Interaction):
        await it.response.send_modal(RsvpRolesModal(view))
    rsvp_roles_btn = make_button(label=t("BTN_RSVP_ROLES", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
    rsvp_roles_btn.callback = rsvp_roles_cb

    if view.wizard_type == "lobby":
        items.append(ui.ActionRow(role_btn, rsvp_roles_btn))
    else:
        # Waiting list limit button
        async def wait_limit_cb(it: discord.Interaction):
            await it.response.send_modal(AdvancedSettingsModal(view))
        wait_limit_btn = make_button(label=t("LBL_WAITLIST_LIMIT", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
        wait_limit_btn.callback = wait_limit_cb

        # Waiting list toggle button
        async def wait_cb(it: discord.Interaction):
            has_global_cap = int(view.data.get("max_accepted") or 0) > 0
            extra_dto = parse_extra_data(view.data.get("extra_data"))
            has_role_cap = any(int(v) > 0 for v in extra_dto.role_limits.values())

            if not has_global_cap and not has_role_cap:
                if not view.data.get("use_waiting_list", False):
                    return await it.response.send_message(
                        t("ERR_WAITLIST_NO_CAP", guild_id=view.guild_id),
                        ephemeral=True,
                    )

            view.data["use_waiting_list"] = not view.data.get("use_waiting_list", False)
            await view.save_to_draft()
            await view.refresh_message(it)

        use_waiting = view.data.get("use_waiting_list", False)
        wait_btn = make_button(
            label=t("SEL_WAIT_ENABLED" if use_waiting else "SEL_WAIT_DISABLED", guild_id=view.guild_id),
            style=discord.ButtonStyle.green if use_waiting else discord.ButtonStyle.gray
        )
        wait_btn.callback = wait_cb

        items.append(ui.ActionRow(wait_btn, wait_limit_btn, role_btn, rsvp_roles_btn))

    # Configuration Category
    items.append(ui.Separator())
    items.append(ui.TextDisplay(f"**{t('LBL_ADV_CAT_CONFIG', guild_id=view.guild_id)}**"))

    # Temp Role Toggle Button
    async def temp_role_cb(it: discord.Interaction):
        view.data["use_temp_role"] = not view.data.get("use_temp_role", False)
        await view.save_to_draft()
        await view.refresh_message(it)
    use_temp = view.data.get("use_temp_role", False)
    temp_role_btn = make_button(
        label=t("LBL_WIZ_TEMP_ROLE", guild_id=view.guild_id) + (f": {t('LBL_TEMP_ROLE_ON', guild_id=view.guild_id)}" if use_temp else f": {t('LBL_TEMP_ROLE_OFF', guild_id=view.guild_id)}"),
        style=discord.ButtonStyle.green if use_temp else discord.ButtonStyle.gray
    )
    temp_role_btn.callback = temp_role_cb

    # Discussion Thread Toggle Button
    async def thread_cb(it: discord.Interaction):
        view.data["use_threads"] = not view.data.get("use_threads", False)
        await view.save_to_draft()
        await view.refresh_message(it)
    use_threads = view.data.get("use_threads", False)
    thread_btn = make_button(
        label=t("LBL_WIZ_THREADS", guild_id=view.guild_id) + (f": {t('LBL_THREADS_ON', guild_id=view.guild_id)}" if use_threads else f": {t('LBL_THREADS_OFF', guild_id=view.guild_id)}"),
        style=discord.ButtonStyle.green if use_threads else discord.ButtonStyle.gray
    )
    thread_btn.callback = thread_cb

    # Creator Button
    async def creator_cb(it: discord.Interaction):
        await it.response.send_modal(CreatorModal(view))
    creator_btn = make_button(label=t("LBL_WIZ_CREATOR", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
    creator_btn.callback = creator_cb

    # Notification / Messages Button
    async def msg_cb(it: discord.Interaction):
        await it.response.send_modal(NotificationSettingsModal(view))
    msg_btn = make_button(label=t("BTN_MESSAGES", guild_id=view.guild_id), style=discord.ButtonStyle.gray)
    msg_btn.callback = msg_cb

    items.append(ui.ActionRow(temp_role_btn, thread_btn, creator_btn, msg_btn))

    # Color Dropdown Selection
    cur_color_raw = view.data.get("color", "0x40c4ff")
    cur_color = cur_color_raw.lower().strip().replace("#", "0x")
    if not cur_color.startswith("0x"):
        cur_color = "0x" + cur_color

    presets = ["0x40c4ff", "0x5865f2", "0xffd700", "0x57f287", "0xeb459e"]
    is_preset = cur_color in presets
    color_opts = [
        make_select_option(label=t("COLOR_DEFAULT", guild_id=view.guild_id), value="0x40c4ff", default=(cur_color == "0x40c4ff")),
        make_select_option(label=t("COLOR_BLURPLE", guild_id=view.guild_id), value="0x5865f2", default=(cur_color == "0x5865f2")),
        make_select_option(label=t("COLOR_GOLD", guild_id=view.guild_id), value="0xffd700", default=(cur_color == "0xffd700")),
        make_select_option(label=t("COLOR_MINT", guild_id=view.guild_id), value="0x57f287", default=(cur_color == "0x57f287")),
        make_select_option(label=t("COLOR_FUCHSIA", guild_id=view.guild_id), value="0xeb459e", default=(cur_color == "0xeb459e")),
        make_select_option(label=t("COLOR_CUSTOM", guild_id=view.guild_id), value="custom", default=(not is_preset))
    ]
    color_sel = ui.Select(placeholder=t("SEL_COLOR", guild_id=view.guild_id), options=color_opts)
    async def color_cb(it: discord.Interaction):
        val = color_sel.values[0]
        if val == "custom":
            await it.response.send_modal(ColorModal(view, cur_color))
        else:
            await it.response.defer()
            view.data["color"] = val
            await view.save_to_draft()
            await view.refresh_message(it)
    color_sel.callback = color_cb

    items.append(ui.TextDisplay(t("LBL_CHOOSE_COLOR", guild_id=view.guild_id)))
    items.append(ui.ActionRow(color_sel))

    # Promotion Notify Selection (Single and Series only)
    if view.wizard_type != "lobby":
        cur_promo_type = view.data.get("notify_promotion") or "none"
        promo_type_opts = [
            make_select_option(label=t("SEL_NOTIFY_NONE", guild_id=view.guild_id), value="none", default=(cur_promo_type == "none")),
            make_select_option(label=t("SEL_NOTIFY_CHANNEL", guild_id=view.guild_id), value="channel", default=(cur_promo_type == "channel")),
            make_select_option(label=t("SEL_NOTIFY_DM", guild_id=view.guild_id), value="dm", default=(cur_promo_type == "dm")),
            make_select_option(label=t("SEL_NOTIFY_BOTH", guild_id=view.guild_id), value="both", default=(cur_promo_type == "both"))
        ]
        promo_type_sel = ui.Select(placeholder=t("LBL_PROMOTION_NOTIFY", guild_id=view.guild_id), options=promo_type_opts)
        async def promo_type_cb(it: discord.Interaction):
            if not view.data.get("use_waiting_list", False):
                return await it.response.send_message(
                    t("ERR_WAITLIST_DISABLED_PROMO", guild_id=view.guild_id),
                    ephemeral=True
                )
            await it.response.defer()
            view.data["notify_promotion"] = promo_type_sel.values[0]
            await view.save_to_draft()
            await view.refresh_message(it)
        promo_type_sel.callback = promo_type_cb

        items.append(ui.TextDisplay(t("LBL_CHOOSE_PROMO_NOTIFY", guild_id=view.guild_id)))
        items.append(ui.ActionRow(promo_type_sel))

    return items
