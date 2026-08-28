import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from utils.emoji_utils import resolve_placeholders
from utils.i18n import t
from utils.logger import log
from utils.lobby_utils import effective_lobby_capacity, lobby_is_full

@dataclass
class ParticipantRosterData:
    """Structured participant roster, capacity, and waiting list data for an event."""
    status_map: Dict[str, List[str]] = field(default_factory=dict)
    total_positive_count: int = 0
    positive_statuses: List[str] = field(default_factory=list)
    role_limits: Dict[str, int] = field(default_factory=dict)
    is_full: bool = False
    computed_status: str = "active"
    role_sections: List[str] = field(default_factory=list)
    waiting_list: List[str] = field(default_factory=list)
    eff_event_cap: int = 0
    status_counts: Dict[str, int] = field(default_factory=dict)
    lobby_cap: Optional[int] = None

class ParticipantFormatter:
    """Pure business logic engine for processing attendee RSVPs, capacity limits, and rosters."""

    @staticmethod
    def extract_role_limits(event_conf: dict, db_event: Optional[dict] = None) -> Dict[str, int]:
        """Extracts and parses role limits from extra_data JSON."""
        extra_data = event_conf.get("extra_data")
        if not extra_data and db_event:
            extra_data = db_event.get("extra_data")
        if extra_data:
            try:
                if isinstance(extra_data, str):
                    return json.loads(extra_data).get("role_limits", {})
                elif isinstance(extra_data, dict):
                    return extra_data.get("role_limits", {})
            except Exception as e:
                log.debug("[ParticipantFormatter] extract_role_limits error: %s", e)
        return {}

    @classmethod
    def format_roster(
        cls,
        active_set: dict,
        rsvps: list,
        event_conf: dict,
        db_event: Optional[dict] = None,
        guild_id: Optional[int] = None,
    ) -> ParticipantRosterData:
        """Processes RSVP records into structured roster groups, role counts, and waitlist."""
        status_map: Dict[str, List[str]] = {opt["id"]: [] for opt in active_set.get("options", [])}
        status_counts: Dict[str, int] = {}
        total_positive_count = 0

        # Determine positive statuses
        positive_statuses = [o["id"] for o in active_set.get("options", []) if o.get("positive")]
        if not positive_statuses and "positive_count" in active_set:
            cnt = active_set["positive_count"]
            positive_statuses = [o["id"] for o in active_set.get("options", [])[:cnt]]

        # Map users to statuses
        for item in rsvps:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                user_id, status = item[0], item[1]
            elif isinstance(item, dict):
                user_id, status = item["user_id"], item["status"]
            else:
                user_id, status = item["user_id"], item["status"]

            status_counts[status] = status_counts.get(status, 0) + 1

            if status not in status_map:
                status_map[status] = []
            status_map[status].append(f"<@{user_id}>")

            if status in positive_statuses:
                total_positive_count += 1

        role_limits = cls.extract_role_limits(event_conf, db_event)
        max_acc = int(event_conf.get("max_accepted") or 0)
        lobby_mode = bool(event_conf.get("lobby_mode"))

        lobby_cap = None
        if lobby_mode:
            lobby_cap = effective_lobby_capacity(max_acc, active_set, role_limits)

        # Capacity fullness calculation
        is_full = False
        if lobby_mode and lobby_cap:
            is_full = lobby_is_full(total_positive_count, lobby_cap)
        elif not lobby_mode:
            is_full = max_acc > 0 and total_positive_count >= max_acc

        eff_event_cap = lobby_cap if (lobby_mode and lobby_cap is not None) else max_acc

        # Computed status (checks lobby expiration)
        status_cfg = event_conf.get("status", "active")
        if (
            lobby_mode
            and status_cfg == "active"
            and event_conf.get("start_time") is None
            and event_conf.get("lobby_expires_at") is not None
            and time.time() > float(event_conf["lobby_expires_at"])
        ):
            status_cfg = "lobby_expired"

        # Build role sections and waiting list
        waiting_list: List[str] = []
        role_sections: List[str] = []

        for opt in active_set.get("options", []):
            role_id = opt["id"]
            users = status_map.get(role_id, [])
            limit = role_limits.get(role_id, opt.get("max_slots"))

            if "list_label_key" in opt:
                label_text = t(opt["list_label_key"], guild_id=guild_id, use_template_lang=True)
            else:
                label_text = opt.get("list_label") or (
                    t(opt["label_key"], guild_id=guild_id, use_template_lang=True)
                    if "label_key" in opt
                    else opt.get("label", "")
                )

            count_text = str(len(users))
            is_pos = role_id in positive_statuses
            if is_pos and max_acc > 0:
                count_text = f"{len(users)}/{max_acc}"
            if limit:
                count_text = f"{len(users)}/{limit}"

            name_parts = []
            if opt.get("emoji"):
                name_parts.append(resolve_placeholders(opt["emoji"]))
            if label_text:
                name_parts.append(label_text)

            name_header = " ".join(name_parts)

            if not opt.get("show_in_list", True):
                role_sections.append(f"**{name_header} ({count_text})**")
            else:
                users_str = ", ".join(users) if users else t("EMBED_NONE", guild_id=guild_id)
                if users:
                    role_sections.append(f"**{name_header} ({count_text}):**\n{users_str}")
                else:
                    role_sections.append(f"**{name_header} ({count_text}):** {users_str}")

            wait_tag = f"wait_{role_id}"
            if wait_tag in status_map:
                emoji = resolve_placeholders(opt.get("emoji", ""))
                for u in status_map[wait_tag]:
                    if limit and emoji:
                        waiting_list.append(f"{u} {emoji}")
                    else:
                        waiting_list.append(u)

        return ParticipantRosterData(
            status_map=status_map,
            total_positive_count=total_positive_count,
            positive_statuses=positive_statuses,
            role_limits=role_limits,
            is_full=is_full,
            computed_status=status_cfg,
            role_sections=role_sections,
            waiting_list=waiting_list,
            eff_event_cap=eff_event_cap,
            status_counts=status_counts,
            lobby_cap=lobby_cap,
        )
