"""
Event UI package for Nexus bot containing live event card renderers, RSVP handlers, and management views.
"""

from .config import (
    get_event_conf,
    get_active_set,
    load_custom_sets,
    CUSTOM_ICON_SETS,
)
from .notifications import (
    send_status_notification,
    send_lobby_fill_notifications,
    notify_promotion,
)
from .lobby import process_lobby_transition
from .rsvp_manager import handle_rsvp, try_promote_waiting
from .participant_formatter import ParticipantFormatter, ParticipantRosterData
from .card_builder import build_card_container, build_card_buttons, update_button_states
from .views import (
    DynamicEventView,
    EditChoiceView,
    StatusChoiceView,
)

async def setup(bot):
    """Extension entry point: loads custom emoji sets from database."""
    await load_custom_sets()

__all__ = [
    "setup",
    "get_event_conf",
    "get_active_set",
    "load_custom_sets",
    "CUSTOM_ICON_SETS",
    "send_status_notification",
    "send_lobby_fill_notifications",
    "notify_promotion",
    "process_lobby_transition",
    "handle_rsvp",
    "try_promote_waiting",
    "ParticipantFormatter",
    "ParticipantRosterData",
    "build_card_container",
    "build_card_buttons",
    "update_button_states",
    "PostponeModal",
    "DynamicEventView",
    "EditChoiceView",
    "StatusChoiceView",
]
