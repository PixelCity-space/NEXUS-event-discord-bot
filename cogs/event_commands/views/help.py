import discord
from discord import ui
from utils.i18n import t
from utils.emoji_utils import make_button

class HelpView(ui.LayoutView):
    """View displaying an interactive command guide and support information."""
    
    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id

    async def build(self):
        self.clear_items()
        gid = self.guild_id

        async def close_cb(it: discord.Interaction):
            await it.response.defer()
            await it.delete_original_response()
        close_btn = make_button(label=t("BTN_CLOSE", guild_id=gid), style=discord.ButtonStyle.secondary)
        close_btn.callback = close_cb

        support_btn = make_button(
            label=t("BTN_SUPPORT", guild_id=gid),
            url="https://discord.gg/PbvX3S7pXR",
            style=discord.ButtonStyle.link
        )

        container_items = [
            ui.TextDisplay(f"### {t('HELP_TITLE', guild_id=gid)}"),
            ui.Separator(),
            ui.TextDisplay(t("HELP_DESC_INTRO", guild_id=gid)),
            ui.Separator(),
            
            ui.TextDisplay(t("HELP_SECTION_USER", guild_id=gid)),
            ui.TextDisplay(f"{t('HELP_CMD_MY_EVENTS', guild_id=gid)}\n{t('HELP_CMD_HISTORY', guild_id=gid)}"),
            ui.Separator(),
            
            ui.TextDisplay(t("HELP_SECTION_MGMT", guild_id=gid)),
            ui.TextDisplay(f"{t('HELP_CMD_CREATE', guild_id=gid)}\n{t('HELP_CMD_LOBBY', guild_id=gid)}\n{t('HELP_CMD_EDIT', guild_id=gid)}\n{t('HELP_CMD_LIST', guild_id=gid)}\n{t('HELP_CMD_STATUS', guild_id=gid)}\n{t('HELP_CMD_EXPORT', guild_id=gid)}\n{t('HELP_CMD_DRAFTS', guild_id=gid)}"),
            ui.Separator(),
            
            ui.TextDisplay(t("HELP_SECTION_ADMIN", guild_id=gid)),
            ui.TextDisplay(f"{t('HELP_CMD_AUDIT', guild_id=gid)}\n{t('HELP_CMD_SETUP', guild_id=gid)}\n{t('HELP_CMD_EMOJIS', guild_id=gid)}\n{t('HELP_CMD_MESSAGES', guild_id=gid)}\n{t('HELP_CMD_RESET', guild_id=gid)}"),
            ui.Separator(),

            ui.TextDisplay(t("HELP_SECTION_REMINDERS", guild_id=gid)),
            ui.TextDisplay(t("HELP_DESC_REMINDERS", guild_id=gid)),
            ui.Separator(),

            ui.TextDisplay(t("HELP_SECTION_TIPS", guild_id=gid)),
            ui.TextDisplay(f"{t('HELP_TIP_LOBBY', guild_id=gid)}\n{t('HELP_TIP_SERIES', guild_id=gid)}\n{t('HELP_TIP_AUDIT', guild_id=gid)}"),
            ui.Separator(),
            
            ui.TextDisplay(t("HELP_PREMIUM_DISCLAIMER", guild_id=gid)),
            ui.Separator(),
            ui.ActionRow(close_btn, support_btn)
        ]

        container = ui.Container(*container_items, accent_color=0x40C4FF)
        self.add_item(container)
