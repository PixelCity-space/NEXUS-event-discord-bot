"""Structured DTO and helper utilities for event extra_data JSON storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union
from utils.logger import log


@dataclass
class EventExtraData:
    """
    Structured DTO model for the `extra_data` JSON field of events.
    Supports strongly-typed accessors, seamless serialization/deserialization,
    and dict-like access for backwards compatibility.
    """
    role_limits: Dict[str, int] = field(default_factory=dict)
    waiting_list_limit: Optional[int] = None
    lobby_auto_start_offset: Optional[str] = None
    custom_promo_msg: Optional[str] = None
    custom_reminder_msg: Optional[str] = None
    thread_id: Optional[int] = None
    recurrence_limit_date: Optional[int] = None
    extra_fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: Union[str, dict, EventExtraData, None]) -> EventExtraData:
        """
        Parses raw input (JSON string, dict, or None) safely into an EventExtraData instance.
        Never raises exceptions; returns empty default instance on invalid input.
        """
        if raw is None:
            return cls()
        if isinstance(raw, cls):
            return raw

        d: dict[str, Any] = {}
        if isinstance(raw, str):
            raw_trimmed = raw.strip()
            if not raw_trimmed:
                return cls()
            try:
                parsed = json.loads(raw_trimmed)
                if isinstance(parsed, dict):
                    d = parsed
            except Exception as e:
                log.debug("[EventExtraData] JSON parse error: %s", e)
                return cls()
        elif isinstance(raw, dict):
            d = raw
        else:
            return cls()

        known_keys = {
            "role_limits",
            "waiting_list_limit",
            "lobby_auto_start_offset",
            "custom_promo_msg",
            "custom_reminder_msg",
            "thread_id",
            "recurrence_limit_date",
        }

        role_limits = d.get("role_limits")
        if not isinstance(role_limits, dict):
            role_limits = {}
        else:
            clean_limits = {}
            for k, v in role_limits.items():
                try:
                    clean_limits[str(k)] = int(v)
                except (ValueError, TypeError):
                    pass
            role_limits = clean_limits

        waiting_list_limit = d.get("waiting_list_limit")
        if waiting_list_limit is not None:
            try:
                waiting_list_limit = int(waiting_list_limit)
            except (ValueError, TypeError):
                waiting_list_limit = None

        thread_id = d.get("thread_id")
        if thread_id is not None:
            try:
                thread_id = int(thread_id)
            except (ValueError, TypeError):
                thread_id = None

        rec_limit_date = d.get("recurrence_limit_date")
        if rec_limit_date is not None:
            try:
                rec_limit_date = int(rec_limit_date)
            except (ValueError, TypeError):
                rec_limit_date = None

        extra_fields = {k: v for k, v in d.items() if k not in known_keys}

        return cls(
            role_limits=role_limits,
            waiting_list_limit=waiting_list_limit,
            lobby_auto_start_offset=d.get("lobby_auto_start_offset"),
            custom_promo_msg=d.get("custom_promo_msg"),
            custom_reminder_msg=d.get("custom_reminder_msg"),
            thread_id=thread_id,
            recurrence_limit_date=rec_limit_date,
            extra_fields=extra_fields,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the DTO to a dictionary suitable for json serialization."""
        res: Dict[str, Any] = {}
        if self.role_limits:
            res["role_limits"] = self.role_limits
        if self.waiting_list_limit is not None:
            res["waiting_list_limit"] = self.waiting_list_limit
        if self.lobby_auto_start_offset is not None:
            res["lobby_auto_start_offset"] = self.lobby_auto_start_offset
        if self.custom_promo_msg is not None:
            res["custom_promo_msg"] = self.custom_promo_msg
        if self.custom_reminder_msg is not None:
            res["custom_reminder_msg"] = self.custom_reminder_msg
        if self.thread_id is not None:
            res["thread_id"] = self.thread_id
        if self.recurrence_limit_date is not None:
            res["recurrence_limit_date"] = self.recurrence_limit_date
        res.update(self.extra_fields)
        return res

    def to_json(self) -> str:
        """Serializes the DTO to a compact JSON string."""
        return json.dumps(self.to_dict())

    # Dict-like compatibility methods
    def get(self, key: str, default: Any = None) -> Any:
        d = self.to_dict()
        return d.get(key, default)

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        return d[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "role_limits" and isinstance(value, dict):
            clean_limits = {}
            for k, v in value.items():
                try:
                    clean_limits[str(k)] = int(v)
                except (ValueError, TypeError):
                    pass
            self.role_limits = clean_limits
        elif key == "waiting_list_limit":
            self.waiting_list_limit = int(value) if value is not None else None
        elif key == "lobby_auto_start_offset":
            self.lobby_auto_start_offset = str(value) if value is not None else None
        elif key == "custom_promo_msg":
            self.custom_promo_msg = str(value) if value is not None else None
        elif key == "custom_reminder_msg":
            self.custom_reminder_msg = str(value) if value is not None else None
        elif key == "thread_id":
            self.thread_id = int(value) if value is not None else None
        elif key == "recurrence_limit_date":
            self.recurrence_limit_date = int(value) if value is not None else None
        else:
            self.extra_fields[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


def parse_extra_data(raw: Union[str, dict, EventExtraData, None]) -> EventExtraData:
    """Helper function to parse any raw extra_data representation into EventExtraData."""
    return EventExtraData.from_raw(raw)


def serialize_extra_data(data: Union[str, dict, EventExtraData, None]) -> str:
    """Helper function to safely serialize any extra_data representation into a JSON string."""
    if data is None:
        return "{}"
    if isinstance(data, EventExtraData):
        return data.to_json()
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return json.dumps(parsed) if isinstance(parsed, dict) else "{}"
        except Exception:
            return "{}"
    if isinstance(data, dict):
        return json.dumps(data)
    return "{}"
