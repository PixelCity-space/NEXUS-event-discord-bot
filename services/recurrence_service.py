from typing import Any, Optional
import datetime
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from dateutil import tz as dttz
from utils.offset_parse import parse_offset
from utils.enums import EventStatus
from utils.extra_data import parse_extra_data

def compute_next_occurrence(
    current_start_ts: float,
    event_conf: dict[str, Any],
) -> Optional[float]:
    """
    Calculates the next start timestamp for recurring events (daily, weekly, custom days, relative, etc.).
    Returns None if recurrence rule cannot be computed or is 'once'.
    """
    if not current_start_ts:
        return None

    tz_str = event_conf.get("timezone", "UTC")
    local_tz = dttz.gettz(tz_str)
    dt = datetime.datetime.fromtimestamp(float(current_start_ts), tz=local_tz)
    rec = event_conf.get("recurrence_type", "once")

    if rec == "daily":
        dt += datetime.timedelta(days=1)
    elif rec == "weekly":
        dt += datetime.timedelta(weeks=1)
    elif rec == "biweekly":
        dt += datetime.timedelta(weeks=2)
    elif rec == "weekdays":
        dt += datetime.timedelta(days=1)
        while dt.weekday() >= 5:
            dt += datetime.timedelta(days=1)
    elif rec == "weekends":
        dt += datetime.timedelta(days=1)
        while dt.weekday() < 5:
            dt += datetime.timedelta(days=1)
    elif rec == "monthly":
        dt += relativedelta(months=1)
    elif rec == "custom":
        raw_cust = event_conf.get("custom_days") or ""
        try:
            days = sorted([int(x.strip()) for x in str(raw_cust).split(",") if x.strip().isdigit()])
            if not days:
                return None

            curr_wd = dt.weekday()
            next_wd = next((d for d in days if d > curr_wd), None)

            if next_wd is not None:
                diff = next_wd - curr_wd
                dt += datetime.timedelta(days=diff)
            else:
                # Wrap around to next week
                diff = (7 - curr_wd) + days[0]
                dt += datetime.timedelta(days=diff)
        except Exception:
            return None
    elif rec == "relative":
        raw_rel = event_conf.get("relative_combo") or ""
        try:
            parts = [p.strip() for p in str(raw_rel).split(",") if p.strip()]
            wk = next((p for p in parts if p.startswith("wk_")), None)
            day = next((p for p in parts if p.startswith("day_")), None)

            if not wk or not day:
                return None

            day_map = {
                "day_monday": 0, "day_tuesday": 1, "day_wednesday": 2,
                "day_thursday": 3, "day_friday": 4, "day_saturday": 5, "day_sunday": 6,
            }
            wd = day_map.get(day)
            if wd is None:
                return None

            target_month = dt + relativedelta(months=1)
            wd_obj_list = [MO, TU, WE, TH, FR, SA, SU]
            wd_obj = wd_obj_list[wd]

            if wk == "wk_first":
                dt = target_month + relativedelta(day=1, weekday=wd_obj(1))
            elif wk == "wk_second":
                dt = target_month + relativedelta(day=1, weekday=wd_obj(2))
            elif wk == "wk_third":
                dt = target_month + relativedelta(day=1, weekday=wd_obj(3))
            elif wk == "wk_fourth":
                dt = target_month + relativedelta(day=1, weekday=wd_obj(4))
            elif wk == "wk_last":
                dt = target_month + relativedelta(day=31, weekday=wd_obj(-1))
            else:
                return None
        except Exception:
            return None
    else:
        return None

    return dt.timestamp()

def compute_repost_time(
    start_ts: float,
    end_ts: Optional[float],
    trigger: str,
    offset_str: str,
    event_conf: dict[str, Any],
) -> Optional[float]:
    """
    Computes the exact timestamp when a recurring event should be reposted to the channel.
    """
    offset = parse_offset(offset_str or "1h")
    offset_seconds = offset.total_seconds()

    if trigger == "before_start":
        next_start = compute_next_occurrence(start_ts, event_conf)
        if next_start is None:
            return None
        return next_start - offset_seconds
    elif trigger == "after_end":
        base_ts = end_ts if end_ts is not None else start_ts
        return base_ts + offset_seconds
    else:  # after_start or default
        return start_ts + offset_seconds

def evaluate_repost_readiness(
    db_event: dict[str, Any],
    event_conf: dict[str, Any],
    now: float,
) -> tuple[bool, Optional[float], Optional[str]]:
    """
    Evaluates whether a recurring event is ready to spawn its next occurrence.
    Returns: (is_ready, next_start_timestamp, terminal_status_if_ended)
    """
    if db_event.get("lobby_mode"):
        return False, None, None

    active_conf = dict(event_conf or {})
    active_conf.update(dict(db_event or {}))

    rec_type = active_conf.get("recurrence_type", "once")
    if rec_type in ("once", "none"):
        return False, None, None

    start_ts = active_conf.get("start_time")
    if not start_ts:
        return False, None, None

    trigger = active_conf.get("repost_trigger", "after_start")
    offset_str = active_conf.get("repost_offset", "1h")
    end_ts = active_conf.get("end_time")

    repost_at = compute_repost_time(float(start_ts), float(end_ts) if end_ts else None, trigger, offset_str, active_conf)
    if repost_at is None or now < repost_at:
        return False, None, None

    next_start = compute_next_occurrence(float(start_ts), active_conf)
    if next_start is None:
        return False, None, "disabled"

    rec_limit = int(db_event.get("recurrence_limit") or 0)
    rec_count = int(db_event.get("recurrence_count") or 0)
    if rec_limit > 0 and (rec_count + 1) >= rec_limit:
        return False, None, "closed"

    extra_dto = parse_extra_data(db_event.get("extra_data"))
    limit_ts = extra_dto.recurrence_limit_date
    if limit_ts and next_start > limit_ts:
        return False, None, EventStatus.CLOSED

    return True, next_start, None

def should_auto_archive_event(
    db_event: dict[str, Any],
    now: float,
    archive_hours: float = 12.0,
) -> bool:
    """
    Determines if a finished one-time event should be automatically closed/archived.
    """
    if db_event.get("status") not in (EventStatus.ACTIVE, EventStatus.RESCHEDULED):
        return False

    rec_type = db_event.get("recurrence_type", "once")
    if rec_type not in ("once", "none"):
        return False

    start_ts = db_event.get("start_time")
    if not start_ts:
        return False

    archive_threshold = archive_hours * 3600.0
    end_ts = db_event.get("end_time")
    reference_ts = float(end_ts) if end_ts else float(start_ts)

    if now > (reference_ts + archive_threshold):
        created_at = db_event.get("created_at") or 0
        if now > (float(created_at) + 900):  # 15 min grace period
            return True

    return False

def is_lobby_expired(
    db_event: dict[str, Any],
    now: float,
) -> bool:
    """
    Checks if a fill-to-start lobby has expired based on its lobby_expires_at timestamp.
    """
    if not db_event.get("lobby_mode"):
        return False
    if (db_event.get("status") or EventStatus.ACTIVE) != EventStatus.ACTIVE:
        return False
    if db_event.get("start_time"):
        return False
    exp = db_event.get("lobby_expires_at")
    if exp is None or now <= float(exp):
        return False
    return True
