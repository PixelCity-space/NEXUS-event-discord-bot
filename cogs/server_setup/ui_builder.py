from typing import Optional, Callable, Any, Awaitable
import discord
from discord import ui
import database
from utils.i18n import t
from utils.emoji_utils import make_select_option, make_button
from .config_schema import SettingDefinition, ServerSettings
from .modals import ValidatedConfigModal

def create_setting_modal_button(
    parent_view,
    setting: SettingDefinition,
    label: str,
    modal_label: str,
    placeholder: str = "",
    is_long: bool = False,
    style: discord.ButtonStyle = discord.ButtonStyle.gray,
    emoji: Optional[Any] = None,
) -> ui.Button:
    """Creates a button that automatically fetches setting value and opens ValidatedConfigModal."""
    btn = make_button(label=label, style=style, emoji=emoji)

    async def callback(interaction: discord.Interaction):
        curr_val = await database.get_guild_setting(
            parent_view.guild_id, setting.key, default=setting.default
        )
        modal = ValidatedConfigModal(
            guild_id=parent_view.guild_id,
            setting=setting,
            label_text=modal_label,
            placeholder=placeholder,
            is_long=is_long,
            default_val=curr_val,
            parent_view=parent_view,
        )
        await interaction.response.send_modal(modal)

    btn.callback = callback
    return btn

def create_setting_toggle_button(
    parent_view,
    setting: SettingDefinition,
    current_value: str,
    label_format: str,
    on_text: str,
    off_text: str,
    pre_toggle_check: Optional[Callable[[bool, discord.Interaction], Awaitable[bool]]] = None,
    save_key_label: Optional[str] = None,
) -> ui.Button:
    """Creates a boolean toggle button with validation hooks and database persistence."""
    is_on = current_value.lower() == "true"
    state_text = on_text if is_on else off_text
    btn_label = label_format.format(state=state_text)
    btn_style = discord.ButtonStyle.success if is_on else discord.ButtonStyle.secondary

    btn = make_button(label=btn_label, style=btn_style)

    async def callback(interaction: discord.Interaction):
        if pre_toggle_check:
            can_toggle = await pre_toggle_check(is_on, interaction)
            if not can_toggle:
                return

        new_val = "false" if is_on else "true"
        await database.save_guild_setting(parent_view.guild_id, setting.key, new_val)
        await parent_view.refresh_message(interaction)
        msg_key = save_key_label or setting.description or setting.key
        await interaction.followup.send(
            t("MSG_SETTING_SAVED", guild_id=parent_view.guild_id, key=msg_key, val=new_val),
            ephemeral=True
        )

    btn.callback = callback
    return btn

def create_color_dropdown(
    parent_view,
    current_color_raw: str,
    setting: SettingDefinition = ServerSettings.DEFAULT_COLOR,
    placeholder: Optional[str] = None,
    modal_label: Optional[str] = None,
    modal_placeholder: Optional[str] = None,
) -> ui.Select:
    """Creates a standard color preset select menu with custom hex modal support."""
    cur_color = (current_color_raw or "0x40c4ff").lower().strip().replace("#", "0x")
    if not cur_color.startswith("0x"):
        cur_color = "0x" + cur_color

    presets = ["0x40c4ff", "0x5865f2", "0xffd700", "0x57f287", "0xeb459e"]
    is_preset = cur_color in presets

    color_opts = [
        make_select_option(label=t("COLOR_DEFAULT", guild_id=parent_view.guild_id), value="0x40c4ff", default=(cur_color == "0x40c4ff")),
        make_select_option(label=t("COLOR_BLURPLE", guild_id=parent_view.guild_id), value="0x5865f2", default=(cur_color == "0x5865f2")),
        make_select_option(label=t("COLOR_GOLD", guild_id=parent_view.guild_id), value="0xffd700", default=(cur_color == "0xffd700")),
        make_select_option(label=t("COLOR_MINT", guild_id=parent_view.guild_id), value="0x57f287", default=(cur_color == "0x57f287")),
        make_select_option(label=t("COLOR_FUCHSIA", guild_id=parent_view.guild_id), value="0xeb459e", default=(cur_color == "0xeb459e")),
        make_select_option(label=t("COLOR_CUSTOM", guild_id=parent_view.guild_id), value="custom", default=(not is_preset))
    ]

    sel_ph = placeholder or t("SEL_COLOR", guild_id=parent_view.guild_id)
    color_sel = ui.Select(placeholder=sel_ph, options=color_opts)

    async def callback(interaction: discord.Interaction):
        val = color_sel.values[0]
        if val == "custom":
            lbl = modal_label or t("SETTING_COLOR", guild_id=parent_view.guild_id)
            ph = modal_placeholder or t("PH_COLOR", guild_id=parent_view.guild_id)
            modal = ValidatedConfigModal(
                guild_id=parent_view.guild_id,
                setting=setting,
                label_text=lbl,
                placeholder=ph,
                default_val=cur_color,
                parent_view=parent_view,
            )
            await interaction.response.send_modal(modal)
        else:
            await database.save_guild_setting(parent_view.guild_id, setting.key, val)
            await parent_view.refresh_message(interaction)
            await interaction.followup.send(
                t("MSG_SETTING_SAVED", guild_id=parent_view.guild_id, key=setting.description or "Color", val=val),
                ephemeral=True
            )

    color_sel.callback = callback
    return color_sel

def create_setting_select(
    parent_view,
    setting: SettingDefinition,
    options: list[discord.SelectOption],
    placeholder: str,
    save_message_key: Optional[str] = None,
    on_change: Optional[Callable[[str, discord.Interaction], Awaitable[None]]] = None,
) -> ui.Select:
    """Creates a select menu that persists selected option to database and updates view."""
    select_menu = ui.Select(placeholder=placeholder, options=options)

    async def callback(interaction: discord.Interaction):
        val = select_menu.values[0]
        await database.save_guild_setting(parent_view.guild_id, setting.key, val)

        if on_change:
            await on_change(val, interaction)

        await parent_view.refresh_message(interaction)
        msg_key = save_message_key or setting.description or setting.key
        await interaction.followup.send(
            t("MSG_SETTING_SAVED", guild_id=parent_view.guild_id, key=msg_key, val=val),
            ephemeral=True
        )

    select_menu.callback = callback
    return select_menu
