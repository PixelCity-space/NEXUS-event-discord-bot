from typing import Any, Optional
import discord
from discord import ui
from ..state import WizardState
from ..actions import process_save_preview, process_publish
from ..sections import (
    build_header_section,
    build_steps_row,
    build_recurrence_section,
    build_settings_section,
    build_notifications_section,
    build_emoji_set_section,
    build_actions_section,
)

class EventWizardView(ui.LayoutView):
    """Main wizard controller view using Discord Components V2 architecture."""

    def __init__(
        self,
        bot: discord.Client,
        creator_id: int,
        existing_data: Optional[dict[str, Any]] = None,
        is_edit: bool = False,
        guild_id: Optional[int] = None,
        bulk_ids: Optional[list[str]] = None,
        wizard_type: Optional[str] = None,
        show_advanced: bool = False,
        show_reminder: bool = False,
        show_recurrence: bool = False,
    ):
        super().__init__(timeout=600)
        self.bot = bot
        self.creator_id = creator_id
        self.guild_id = guild_id
        self.is_edit = is_edit
        self.bulk_ids = bulk_ids

        # Form state manager
        self.state = WizardState(
            bot=bot,
            creator_id=creator_id,
            guild_id=guild_id,
            existing_data=existing_data,
            is_edit=is_edit,
            bulk_ids=bulk_ids,
            wizard_type=wizard_type,
        )

        # UI toggle states
        self.show_advanced = show_advanced
        self.show_reminder = show_reminder
        self.show_recurrence = show_recurrence

    @property
    def data(self) -> dict[str, Any]:
        return self.state.data

    @data.setter
    def data(self, value: dict[str, Any]) -> None:
        self.state.data = value

    @property
    def wizard_type(self) -> str:
        return self.state.wizard_type

    @wizard_type.setter
    def wizard_type(self, value: str) -> None:
        self.state.wizard_type = value

    @property
    def steps_completed(self) -> dict[str, bool]:
        return self.state.steps_completed

    @steps_completed.setter
    def steps_completed(self, value: dict[str, bool]) -> None:
        self.state.steps_completed = value

    @property
    def can_publish(self) -> bool:
        return self.state.can_publish

    @can_publish.setter
    def can_publish(self, value: bool) -> None:
        self.state.can_publish = value

    @property
    def chan_warning(self) -> str:
        return self.state.chan_warning

    @chan_warning.setter
    def chan_warning(self, value: str) -> None:
        self.state.chan_warning = value

    @property
    def icon_set_options(self) -> list[discord.SelectOption]:
        return self.state.icon_set_options

    @icon_set_options.setter
    def icon_set_options(self, value: list[discord.SelectOption]) -> None:
        self.state.icon_set_options = value

    @property
    def recurrence_options(self) -> list[discord.SelectOption]:
        return self.state.recurrence_options

    @recurrence_options.setter
    def recurrence_options(self, value: list[discord.SelectOption]) -> None:
        self.state.recurrence_options = value

    def get_status_text(self) -> str:
        return self.state.get_status_text()

    async def refresh_ui_data(self) -> None:
        await self.state.load_defaults()

    async def save_to_draft(self) -> None:
        await self.state.save_to_draft()

    async def handle_save_preview(self, interaction: discord.Interaction) -> None:
        await process_save_preview(self, interaction)

    async def publish_btn(self, interaction: discord.Interaction) -> None:
        await process_publish(self, interaction)

    async def refresh_message(self, interaction: discord.Interaction, send_followup: bool = False) -> None:
        """Assembles all sections into a Discord Components V2 container and renders."""
        view = EventWizardView(
            bot=self.bot,
            creator_id=self.creator_id,
            existing_data=self.data,
            is_edit=self.is_edit,
            guild_id=self.guild_id,
            bulk_ids=self.bulk_ids,
            wizard_type=self.wizard_type,
            show_advanced=self.show_advanced,
            show_reminder=self.show_reminder,
            show_recurrence=self.show_recurrence,
        )
        view.can_publish = self.can_publish
        view.clear_items()
        await view.refresh_ui_data()

        # Build UI layout components from modular sections
        container_items: list[ui.Item] = []
        container_items.extend(build_header_section(view))
        container_items.append(build_steps_row(view))

        if view.show_advanced:
            container_items.extend(build_settings_section(view))
        elif view.show_recurrence and view.wizard_type == "series":
            container_items.extend(build_recurrence_section(view))
        elif view.show_reminder:
            container_items.extend(build_notifications_section(view))

        container_items.extend(build_emoji_set_section(view))
        container_items.extend(build_actions_section(view))

        view.add_item(ui.Container(*container_items, accent_color=0x40C4FF))

        if send_followup:
            await interaction.followup.send(view=view, ephemeral=True)
        elif interaction.response.is_done():
            await interaction.edit_original_response(view=view)
        else:
            await interaction.response.edit_message(view=view)
