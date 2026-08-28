"""
Compatibility module re-exporting event and emoji set configurations from utils.templates.
"""

from utils.templates import (
    CUSTOM_ICON_SETS,
    get_event_conf,
    load_custom_sets,
    get_active_set,
)

__all__ = [
    "CUSTOM_ICON_SETS",
    "get_event_conf",
    "load_custom_sets",
    "get_active_set",
]
