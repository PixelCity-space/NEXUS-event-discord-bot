from .cog import ServerSetupCog
from .base_view import BaseSetupView
from .config_schema import ServerSettings, SettingDefinition
from .modals import ValidatedConfigModal, MultiReminderOffsetModal, SimpleConfigModal
from .views import (
    ServerSetupView,
    GeneralSetupView,
    ReminderSetupView,
    EventDefaultsView,
)

from .ui_builder import (
    create_setting_modal_button,
    create_setting_toggle_button,
    create_color_dropdown,
    create_setting_select,
)

async def setup(bot):
    """Discord.py extension entry point."""
    await bot.add_cog(ServerSetupCog(bot))

__all__ = [
    "setup",
    "ServerSetupCog",
    "BaseSetupView",
    "ServerSettings",
    "SettingDefinition",
    "ValidatedConfigModal",
    "MultiReminderOffsetModal",
    "SimpleConfigModal",
    "create_setting_modal_button",
    "create_setting_toggle_button",
    "create_color_dropdown",
    "create_setting_select",
    "ServerSetupView",
    "GeneralSetupView",
    "ReminderSetupView",
    "EventDefaultsView",
]
