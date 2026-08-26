import time
import database
from .notifications import send_lobby_fill_notifications

async def process_lobby_transition(bot, event_id: str, active_set: dict, guild_id_int: int):
    """Checks lobby capacity and transitions start time when full or reopens when unfilled."""
    from utils.lobby_utils import (
        count_positive_rsvps,
        effective_lobby_capacity,
        lobby_is_full,
        positive_status_ids,
        role_limits_from_extra,
    )

    db_event = await database.get_active_event(event_id)
    if not db_event or not db_event.get("lobby_mode"):
        return

    pos = positive_status_ids(active_set)
    rl = role_limits_from_extra(db_event.get("extra_data"))
    cap = effective_lobby_capacity(int(db_event.get("max_accepted") or 0), active_set, rl)
    if cap is None or cap <= 0:
        return

    rsvps = await database.get_rsvps(event_id)
    cnt = count_positive_rsvps(rsvps, pos)
    had_start = db_event.get("start_time") is not None
    full = lobby_is_full(cnt, cap)

    if full and not had_start:
        await database.set_lobby_start_time(event_id, time.time())
        db_event = await database.get_active_event(event_id)
        await send_lobby_fill_notifications(bot, db_event, active_set, guild_id_int)
    elif not full and had_start:
        await database.set_lobby_start_time(event_id, None)
