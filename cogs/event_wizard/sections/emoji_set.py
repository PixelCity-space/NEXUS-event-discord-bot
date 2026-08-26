import discord
from discord import ui
from utils.i18n import t

def build_emoji_set_section(view) -> list[ui.Item]:
    """Builds the emoji / icon set dropdown selection."""
    sel_icon = ui.Select(placeholder=t("SEL_ICON_SET", guild_id=view.guild_id), options=view.icon_set_options)

    async def icon_cb(it: discord.Interaction):
        await it.response.defer()
        view.data["icon_set"] = sel_icon.values[0]
        await view.save_to_draft()
        await view.refresh_message(it)

    sel_icon.callback = icon_cb

    return [
        ui.Separator(),
        ui.TextDisplay(t("LBL_CHOOSE_EMOJI_SET", guild_id=view.guild_id)),
        ui.ActionRow(sel_icon)
    ]
