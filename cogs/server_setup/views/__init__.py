from .registry import register_view, get_view
from .main_menu import ServerSetupView
from .general import GeneralSetupView
from .reminders import ReminderSetupView
from .event_defaults import EventDefaultsView

__all__ = [
    "register_view",
    "get_view",
    "ServerSetupView",
    "GeneralSetupView",
    "ReminderSetupView",
    "EventDefaultsView",
]
