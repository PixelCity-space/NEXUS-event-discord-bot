import re
from dataclasses import dataclass
from typing import Callable, Any, Optional
from database import DEFAULT_TIMEZONE

@dataclass
class SettingDefinition:
    key: str
    default: Any
    validator: Optional[Callable[[str], tuple[bool, Optional[str]]]] = None
    requires_reload: bool = False
    description: str = ""

def validate_positive_int(val: str) -> tuple[bool, Optional[str]]:
    """Validate that the given value is a non-negative integer."""
    cleaned = val.strip()
    if cleaned.isdigit() and int(cleaned) >= 0:
        return True, None
    return False, "Only positive integers or 0 are allowed!"

def validate_hex_color(val: str) -> tuple[bool, Optional[str]]:
    """Validate hexadecimal color format (e.g. 0x40C4FF or #40C4FF)."""
    cleaned = val.strip().replace("#", "").replace("0x", "").replace("0X", "")
    if re.fullmatch(r"^[0-9a-fA-F]{6}$", cleaned):
        return True, None
    return False, "Invalid color format! Use a 6-digit hex code (e.g. 0x40C4FF or #40C4FF)."

def validate_offset_list(val: str) -> tuple[bool, Optional[str]]:
    """Validate reminder offset list format (e.g. 15m, 1h, 1d, etc.)."""
    cleaned = val.strip()
    if not cleaned:
        return True, None
    
    valid_pattern = re.compile(r"^(\d+)([mhd])(?:,([^,]*))?(?:,(.*))?$", re.IGNORECASE)
    lines = [x.strip() for x in cleaned.splitlines() if x.strip()]
    for line in lines:
        if not valid_pattern.match(line):
            return False, f"Invalid offset format: '{line}'. Use format like '15m', '2h', or '1d'."
    return True, None

def validate_non_empty(val: str) -> tuple[bool, Optional[str]]:
    """Validate that the field is not empty."""
    if val and val.strip():
        return True, None
    return False, "Field cannot be empty!"

class ServerSettings:
    TIMEZONE = SettingDefinition(
        key="timezone",
        default=DEFAULT_TIMEZONE,
        validator=validate_non_empty,
        description="Default server timezone"
    )
    DEFAULT_COLOR = SettingDefinition(
        key="default_color",
        default="0x40C4FF",
        validator=validate_hex_color,
        description="Default embed color hex code"
    )
    LANGUAGE = SettingDefinition(
        key="language",
        default="en",
        requires_reload=True,
        description="Bot language for the guild"
    )
    ADMIN_ROLE_IDS = SettingDefinition(
        key="admin_role_ids",
        default="",
        requires_reload=True,
        description="Comma/newline-separated list of admin role IDs"
    )
    ADMIN_CHANNEL_IDS = SettingDefinition(
        key="admin_channel_ids",
        default="",
        requires_reload=True,
        description="Comma/newline-separated list of admin channel IDs"
    )
    TEMPLATE_LANGUAGE = SettingDefinition(
        key="template_language",
        default="en",
        requires_reload=True,
        description="Event templates language"
    )
    DEFAULT_REMINDER_OFFSET = SettingDefinition(
        key="default_reminder_offset",
        default="",
        validator=validate_offset_list,
        description="Default reminder offsets"
    )
    STATUS_NOTIFICATION_TYPE = SettingDefinition(
        key="status_notification_type",
        default="none",
        description="Status change notification channel type"
    )
    DEFAULT_EVENT_CHANNEL = SettingDefinition(
        key="default_event_channel",
        default="",
        description="Default event channel reference or ID"
    )
    DEFAULT_MAX_PARTICIPANTS = SettingDefinition(
        key="default_max_participants",
        default="0",
        validator=validate_positive_int,
        description="Default maximum participant capacity"
    )
    DEFAULT_USE_WAITING_LIST = SettingDefinition(
        key="default_use_waiting_list",
        default="false",
        description="Enable waiting list by default"
    )
    DEFAULT_REPOST_OFFSET = SettingDefinition(
        key="default_repost_offset",
        default="12h",
        description="Default repost offset interval"
    )
    DEFAULT_REPOST_TRIGGER = SettingDefinition(
        key="default_repost_trigger",
        default="after_end",
        description="Default repost trigger timing"
    )
    DEFAULT_USE_TEMP_ROLE = SettingDefinition(
        key="default_use_temp_role",
        default="false",
        description="Enable temporary event roles by default"
    )
    AUTO_ARCHIVE_HOURS = SettingDefinition(
        key="auto_archive_hours",
        default="12",
        validator=validate_positive_int,
        description="Hours before auto-archiving finished events"
    )
    DEFAULT_NOTIFY_PROMOTION = SettingDefinition(
        key="default_notify_promotion",
        default="none",
        description="Notification mode when promoted from waiting list"
    )

    # Dictionary indexed by key for fast lookup
    _BY_KEY = {
        setting.key: setting 
        for setting in [
            TIMEZONE, DEFAULT_COLOR, LANGUAGE, ADMIN_ROLE_IDS, ADMIN_CHANNEL_IDS,
            TEMPLATE_LANGUAGE, DEFAULT_REMINDER_OFFSET, STATUS_NOTIFICATION_TYPE,
            DEFAULT_EVENT_CHANNEL, DEFAULT_MAX_PARTICIPANTS, DEFAULT_USE_WAITING_LIST,
            DEFAULT_REPOST_OFFSET, DEFAULT_REPOST_TRIGGER, DEFAULT_USE_TEMP_ROLE,
            AUTO_ARCHIVE_HOURS, DEFAULT_NOTIFY_PROMOTION
        ]
    }

    @classmethod
    def get_by_key(cls, key: str) -> Optional[SettingDefinition]:
        return cls._BY_KEY.get(key)
