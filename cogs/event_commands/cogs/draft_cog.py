import json
import discord
from discord.ext import commands
from discord import app_commands
import database
from utils.i18n import t

class DraftCommands(commands.GroupCog, name="draft"):
    """Cog for users to manage their event drafts."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="continue", description="Finish an event you started earlier")
    async def continue_draft(self, interaction: discord.Interaction, draft_id: str):
        await interaction.response.defer(ephemeral=True)
        record = await database.get_draft(draft_id, interaction.guild_id)
        if not record: 
            return await interaction.followup.send(t("ERR_DRAFT_NOT_FOUND"), ephemeral=True)
        
        data = record["data"]
        if isinstance(data, str):
            data = json.loads(data)

        from cogs.event_wizard import EventWizardView
        view = EventWizardView(self.bot, interaction.user.id, existing_data=data, guild_id=interaction.guild_id)
        await view.refresh_message(interaction)

    @continue_draft.autocomplete("draft_id")
    async def continue_draft_autocomplete(self, interaction: discord.Interaction, current: str):
        drafts = await database.get_user_drafts(interaction.guild_id, interaction.user.id)
        choices = []
        for d in drafts:
            label = f"{d['title']} ({d['draft_id']})"
            if current.lower() in label.lower(): 
                choices.append(app_commands.Choice(name=label[:100], value=d['draft_id']))
        return choices[:25]

    @app_commands.command(name="delete", description="Delete one of your drafts")
    async def delete_draft_cmd(self, interaction: discord.Interaction, draft_id: str):
        await database.delete_draft(draft_id, interaction.guild_id)
        await interaction.response.send_message(t("MSG_DRAFT_DELETED"), ephemeral=True)

    @delete_draft_cmd.autocomplete("draft_id")
    async def delete_draft_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.continue_draft_autocomplete(interaction, current)

    @app_commands.command(name="delete-all", description="Delete all your drafts at once")
    async def delete_all_drafts(self, interaction: discord.Interaction):
        await database.delete_all_user_drafts(interaction.guild_id, interaction.user.id)
        await interaction.response.send_message(t("MSG_DRAFTS_CLEARED"), ephemeral=True)
