"""
Database package for Nexus bot with repository-based architecture.
"""

from .connection import (
    DEFAULT_TIMEZONE,
    MAX_EVENT_REMINDERS,
    DatabaseManager,
    db_manager,
    create_pool,
    set_pool,
    get_pool,
    init_db,
)

from .repositories.reminders import (
    normalize_reminders_for_store,
    normalize_reminder_message_for_store,
    get_event_reminders,
    get_all_active_reminders_batch,
    replace_event_reminders,
    mark_reminder_slot_sent,
    mark_all_reminder_slots_sent,
    mark_reminder_sent,
)

from .repositories.events import (
    normalize_rsvp_allowed_role_ids_value,
    normalize_image_urls_for_store,
    check_config_exists,
    create_active_event,
    get_active_events,
    get_active_events_by_config,
    get_active_event,
    update_active_event,
    update_event_status,
    update_event_status_bulk,
    update_event_time,
    set_lobby_start_time,
    update_active_events_metadata_bulk,
    set_event_message,
    delete_active_event,
    get_endable_events,
    get_user_active_events,
    get_user_event_history,
    get_guild_events_export,
)

from .repositories.rsvps import (
    get_rsvps,
    update_rsvp,
    join_or_update_rsvp_atomic,
    get_rsvps_with_time,
    promote_next_waiting,
    promote_waiting_users_atomic,
    get_attendance_eligible_events,
    get_event_attendance_data,
    update_rsvp_attendance,
    get_guild_reliability_stats,
    get_event_reliability_audit,
    get_guild_rsvps_export,
)

from .repositories.drafts import (
    save_draft,
    get_draft,
    delete_draft,
    get_user_drafts,
    delete_all_user_drafts,
)

from .repositories.settings import (
    save_guild_setting,
    get_guild_setting,
    get_all_guild_settings,
    save_global_setting,
    get_global_setting,
    save_guild_translation,
    get_guild_translations,
    delete_guild_translation,
    reset_guild_data,
    get_global_stats,
)

from .repositories.emojis import (
    save_emoji_set,
    get_emoji_sets,
    get_all_custom_emoji_sets,
    delete_emoji_set,
    save_global_emoji_set,
    get_all_global_emoji_sets,
    delete_global_emoji_set,
    clear_global_emoji_sets,
)

__all__ = [
    # Connection
    "DEFAULT_TIMEZONE",
    "MAX_EVENT_REMINDERS",
    "DatabaseManager",
    "db_manager",
    "create_pool",
    "set_pool",
    "get_pool",
    "init_db",
    # Normalizers
    "normalize_reminders_for_store",
    "normalize_reminder_message_for_store",
    "normalize_rsvp_allowed_role_ids_value",
    "normalize_image_urls_for_store",
    # Reminders
    "get_event_reminders",
    "get_all_active_reminders_batch",
    "replace_event_reminders",
    "mark_reminder_slot_sent",
    "mark_all_reminder_slots_sent",
    "mark_reminder_sent",
    # Events
    "check_config_exists",
    "create_active_event",
    "get_active_events",
    "get_active_events_by_config",
    "get_active_event",
    "update_active_event",
    "update_event_status",
    "update_event_status_bulk",
    "update_event_time",
    "set_lobby_start_time",
    "update_active_events_metadata_bulk",
    "set_event_message",
    "delete_active_event",
    "get_endable_events",
    "get_user_active_events",
    "get_user_event_history",
    "get_guild_events_export",
    # RSVPs
    "get_rsvps",
    "update_rsvp",
    "join_or_update_rsvp_atomic",
    "get_rsvps_with_time",
    "promote_next_waiting",
    "promote_waiting_users_atomic",
    "get_attendance_eligible_events",
    "get_event_attendance_data",
    "update_rsvp_attendance",
    "get_guild_reliability_stats",
    "get_event_reliability_audit",
    "get_guild_rsvps_export",
    # Drafts
    "save_draft",
    "get_draft",
    "delete_draft",
    "get_user_drafts",
    "delete_all_user_drafts",
    # Settings & Translations
    "save_guild_setting",
    "get_guild_setting",
    "get_all_guild_settings",
    "save_global_setting",
    "get_global_setting",
    "save_guild_translation",
    "get_guild_translations",
    "delete_guild_translation",
    "reset_guild_data",
    "get_global_stats",
    # Emojis
    "save_emoji_set",
    "get_emoji_sets",
    "get_all_custom_emoji_sets",
    "delete_emoji_set",
    "save_global_emoji_set",
    "get_all_global_emoji_sets",
    "delete_global_emoji_set",
    "clear_global_emoji_sets",
]
