import discord
from discord import ui
from utils.i18n import t
from utils.emoji_utils import make_button

def build_actions_section(view) -> list[ui.Item]:
    """Builds the bottom action row with Save & Preview and Publish buttons."""
    save_style = discord.ButtonStyle.green
    save_btn = make_button(
        label=t("BTN_SAVE_PREVIEW", guild_id=view.guild_id),
        style=save_style,
        disabled=view.can_publish
    )
    async def save_cb(it: discord.Interaction):
        await view.handle_save_preview(it)
    save_btn.callback = save_cb

    pub_row: list[ui.Button] = [save_btn]

    if view.can_publish:
        pub_btn = make_button(
            label=t("BTN_PUBLISH", guild_id=view.guild_id),
            style=discord.ButtonStyle.green
        )
        async def pub_cb(it: discord.Interaction):
            await view.publish_btn(it)
        pub_btn.callback = pub_cb
        pub_row.append(pub_btn)

    return [
        ui.Separator(),
        ui.ActionRow(*pub_row)
    ]
