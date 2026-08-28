from enum import Enum

class EventStatus(str, Enum):
    """Event lifecycle status enumeration."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"
    DELETED = "deleted"
    CLOSED = "closed"
    ENDED = "ended"
    RESCHEDULED = "rescheduled"
    LOBBY_EXPIRED = "lobby_expired"

    @property
    def is_interactive(self) -> bool:
        """Returns True if user interactions (RSVP, button clicks) are accepted."""
        return self in (EventStatus.ACTIVE, EventStatus.RESCHEDULED)

    @property
    def is_terminal(self) -> bool:
        """Returns True if the event has ended or reached a terminal non-interactive state."""
        return self in (
            EventStatus.CANCELLED,
            EventStatus.DELETED,
            EventStatus.CLOSED,
            EventStatus.ENDED,
            EventStatus.LOBBY_EXPIRED,
        )

    def __str__(self) -> str:
        return self.value

class AttendanceStatus(str, Enum):
    """User RSVP attendance confirmation status."""
    PRESENT = "present"
    NO_SHOW = "no_show"

    def __str__(self) -> str:
        return self.value

class RecurrenceType(str, Enum):
    """Event recurrence scheduling pattern."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

    def __str__(self) -> str:
        return self.value
