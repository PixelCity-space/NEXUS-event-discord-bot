import discord
from discord import ui
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import make_button

class EmojiHelpView(ui.LayoutView):
    """Ephemeral help guide for the custom emoji & role sets configuration."""
    
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    async def prepare(self):
        self.clear_items()
        
        async def close_callback(interaction: discord.Interaction):
            try:
                await interaction.response.defer()
                await interaction.delete_original_response()
            except Exception as e:
                log.error(f"[EmojiWizard] Error in EmojiHelpView close_callback: {e}", exc_info=True)

        close_btn = make_button(
            label=t("BTN_CLOSE", guild_id=self.guild_id), 
            style=discord.ButtonStyle.secondary
        )
        close_btn.callback = close_callback

        container = ui.Container(
            ui.TextDisplay(f"### {t('HELP_EMOJI_TITLE', guild_id=self.guild_id)}"),
            ui.Separator(),
            ui.TextDisplay(t("HELP_EMOJI_DESC", guild_id=self.guild_id)),
            ui.Separator(),
            ui.ActionRow(close_btn),
            accent_color=0x40C4FF
        )
        self.add_item(container)

async def send_emoji_help(interaction: discord.Interaction, guild_id: int):
    """Sends the ephemeral help guide ensuring the view is prepared for stable interaction."""
    view = EmojiHelpView(guild_id)
    await view.prepare()
    await interaction.response.send_message(view=view, ephemeral=True)
