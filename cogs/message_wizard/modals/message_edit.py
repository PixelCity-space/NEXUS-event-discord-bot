from typing import Any
import discord
from discord import ui
import database
from utils.i18n import t, load_guild_translations

class MessageEditModal(ui.Modal):
    """Modal to edit custom translation overrides for a specific language key."""
    
    def __init__(self, wizard_view: Any, key: str, current_val: str, guild_id: str):
        super().__init__(title=t("MODAL_MESSAGE_EDIT", guild_id=guild_id))
        self.wizard_view = wizard_view
        self.key = key
        self.guild_id = str(guild_id)
        
        self.text_input = ui.TextInput(
            label=f"{t('LBL_CUSTOM_TEXT', guild_id=guild_id)}: {key}"[:45],
            placeholder=f"{t('LBL_VARIABLES', guild_id=guild_id)}: {{user_id}}, {{title}}...",
            default=current_val,
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await database.save_guild_translation(self.guild_id, self.key, self.text_input.value)
        await load_guild_translations(self.wizard_view.guild_id)
        await interaction.followup.send(
            t("MSG_KEY_SAVED", guild_id=self.wizard_view.guild_id, key=self.key), 
            ephemeral=True
        )
        await self.wizard_view.refresh_message(interaction)
