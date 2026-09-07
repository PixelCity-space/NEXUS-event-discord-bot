from typing import Any, Optional
import discord
import database
from utils.offset_parse import parse_offset
from utils.i18n import t
from utils.text_utils import safe_format
from utils.templates import get_active_set
from services.notification_service import resolve_target_recipients, send_event_alert

async def handle_reminders(
    bot: discord.Client,
    db_event: dict[str, Any],
    now: float,
    preloaded_reminders: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Processes scheduled multi-slot reminders for active events."""
    if db_event.get("lobby_mode"):
        return

    event_id = db_event["event_id"]
    guild_id = db_event.get("guild_id")
    start_ts = db_event.get("start_time")
    if start_ts is None:
        return

    if preloaded_reminders is not None:
        rows = preloaded_reminders
    else:
        rows = list(await database.get_event_reminders(event_id))
    legacy_only = False
    if not rows and db_event.get("reminder_offset"):
        if int(db_event.get("reminder_sent") or 0) == 1:
            return
        rows = [
            {"slot_idx": 0, "offset_str": db_event.get("reminder_offset", ""), "sent": 0}
        ]
        legacy_only = True

    due = []
    for r in rows:
        if int(r["sent"] or 0) == 1:
            continue
        rem_ts = start_ts - parse_offset(r["offset_str"]).total_seconds()
        if now >= rem_ts:
            due.append(r)
    if not due:
        return

    due.sort(key=lambda x: int(x["slot_idx"]))

    rsvps = await database.get_rsvps(event_id)
    if not rsvps:
        if legacy_only:
            await database.mark_reminder_sent(event_id)
        else:
            await database.mark_all_reminder_slots_sent(event_id)
        return

    global_rem_type = (db_event.get("reminder_type") or "none").lower()
    shared_custom_msg = (db_event.get("reminder_message") or "").strip() or None
    temp_role_id = db_event.get("temp_role_id")
    active_set = get_active_set(db_event.get("icon_set", "standard"))

    for r in due:
        target_raw = r.get("target") or "coming"
        target_user_ids = resolve_target_recipients(
            bot=bot,
            db_event=db_event,
            target_raw=target_raw,
            rsvps=rsvps,
            active_set=active_set,
        )

        if not target_user_ids:
            if legacy_only:
                await database.mark_reminder_sent(event_id)
            else:
                await database.mark_reminder_slot_sent(event_id, int(r["slot_idx"]))
            continue

        local_type = (r.get("method") or global_rem_type or "ping").lower()
        if local_type == "none":
            if legacy_only:
                await database.mark_reminder_sent(event_id)
            else:
                await database.mark_reminder_slot_sent(event_id, int(r["slot_idx"]))
            continue

        rem_text_raw = r.get("custom_message") or shared_custom_msg
        if rem_text_raw:
            rem_text = safe_format(rem_text_raw, title=db_event.get("title", ""))
        else:
            rem_text = t("MSG_REM_DESC", guild_id=guild_id, title=db_event.get("title", ""))

        embed = discord.Embed(
            title=t("LBL_REMINDER_TITLE", guild_id=guild_id),
            description=rem_text,
            color=discord.Color.orange(),
        )
        embed.add_field(
            name=t("LBL_STARTS", guild_id=guild_id),
            value=f"<t:{int(start_ts)}:R>",
        )

        # Determine temp role usage for mentions
        effective_temp_role = temp_role_id if target_raw.lower() in ("all",) else None

        await send_event_alert(
            bot=bot,
            channel_id=db_event.get("channel_id"),
            target_user_ids=target_user_ids,
            method=local_type,
            embed=embed,
            temp_role_id=effective_temp_role,
        )

        if legacy_only:
            await database.mark_reminder_sent(event_id)
        else:
            await database.mark_reminder_slot_sent(event_id, int(r["slot_idx"]))
