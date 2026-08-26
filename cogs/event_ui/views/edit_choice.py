import discord
from utils.emoji_utils import make_button
from utils.i18n import t

class EditChoiceView(discord.ui.View):
    """Prompt view to choose between editing a single instance or the entire series."""
    
    def __init__(self, bot, event_id: str, db_event: dict, series_events: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.db_event = db_event
        self.series_events = series_events
        guild_id = db_event.get("guild_id")
        
        btn_single = make_button(label=t("BTN_SINGLE_INSTANCE", guild_id=guild_id), style=discord.ButtonStyle.secondary)
        btn_single.callback = self.edit_single_callback
        self.add_item(btn_single)
        
        btn_series = make_button(label=t("BTN_ENTIRE_SERIES", guild_id=guild_id), style=discord.ButtonStyle.primary)
        btn_series.callback = self.edit_series_callback
        self.add_item(btn_series)

    async def edit_single_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from .dynamic_card import DynamicEventView
        await DynamicEventView(self.bot, self.event_id)._open_wizard(interaction, self.db_event)

    async def edit_series_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from .dynamic_card import DynamicEventView
        await DynamicEventView(self.bot, self.event_id)._open_wizard(
            interaction, self.db_event, bulk_ids=[ev['event_id'] for ev in self.series_events]
        )
