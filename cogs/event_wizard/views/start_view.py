import discord
from discord import ui
from utils.emojis import ERROR
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import make_button

class WizardStartView(ui.LayoutView):
    """Initial choice view: Single vs Recurring event wizard using Components V2."""
    
    def __init__(self, bot, creator_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.creator_id = creator_id
        self.guild_id = guild_id

    async def refresh_message(self, interaction: discord.Interaction):
        # Deferred import to prevent circular dependencies
        from .wizard_view import EventWizardView

        view = WizardStartView(self.bot, self.creator_id, self.guild_id)
        view.clear_items()
        
        guild_id = self.guild_id
        title = t("WIZARD_TITLE", guild_id=guild_id)
        desc = t("WIZARD_TYPE_DESC", guild_id=guild_id) + "\n" + t("WIZARD_TYPE_LOBBY_HINT", guild_id=guild_id)
        
        # Action Buttons
        single_btn = make_button(
            label=t("BTN_SINGLE_EVENT", guild_id=guild_id),
            style=discord.ButtonStyle.secondary
        )
        async def single_cb(it: discord.Interaction):
            try:
                log.info(f"[Wizard] Single event button clicked by {it.user.id}")
                new_view = EventWizardView(self.bot, self.creator_id, guild_id=self.guild_id, wizard_type="single")
                await new_view.refresh_message(it)
            except Exception as e:
                log.error(f"[Wizard] Error in single_cb: {e}", exc_info=True)
                if not it.response.is_done():
                    await it.response.send_message(f"{ERROR} {e}", ephemeral=True)

        single_btn.callback = single_cb
        
        recurring_btn = make_button(
            label=t("BTN_RECURRING_EVENT", guild_id=guild_id),
            style=discord.ButtonStyle.secondary
        )
        async def recurring_cb(it: discord.Interaction):
            try:
                log.info(f"[Wizard] Recurring series button clicked by {it.user.id}")
                new_view = EventWizardView(self.bot, self.creator_id, guild_id=self.guild_id, wizard_type="series")
                await new_view.refresh_message(it)
            except Exception as e:
                log.error(f"[Wizard] Error in recurring_cb: {e}", exc_info=True)
                if not it.response.is_done():
                    await it.response.send_message(f"{ERROR} {e}", ephemeral=True)

        recurring_btn.callback = recurring_cb
        
        row = ui.ActionRow(single_btn, recurring_btn)
        
        container = ui.Container(
            ui.TextDisplay(f"### {title}"),
            ui.Separator(),
            ui.TextDisplay(desc),
            ui.Separator(),
            row,
            accent_color=0x40C4FF
        )
        view.add_item(container)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, embeds=[], view=view)
        elif interaction.type == discord.InteractionType.component:
            await interaction.response.edit_message(content=None, embeds=[], view=view)
        else:
            await interaction.response.send_message(view=view, ephemeral=True)
