import time
import random
import datetime
from typing import Optional
import discord
from utils.emojis import WARNING, COUNTDOWN
from utils.emoji_utils import to_emoji, make_button
from utils.i18n import t
from utils.enums import EventStatus
from utils.calendar_utils import get_google_calendar_url, get_outlook_calendar_url, get_yahoo_calendar_url
from utils.extra_data import parse_extra_data
from .participant_formatter import ParticipantFormatter, ParticipantRosterData

def build_card_container(
    bot: discord.Client,
    event_id: str,
    event_conf: dict,
    db_event: Optional[dict],
    active_set: dict,
    rsvps: list,
) -> discord.ui.Container:
    """Builds the Discord UI Components V2 Container holding the event details and attendee rosters."""
    guild_id = event_conf.get("guild_id")

    # Format attendee rosters and capacity data via ParticipantFormatter
    roster_data: ParticipantRosterData = ParticipantFormatter.format_roster(
        active_set=active_set,
        rsvps=rsvps,
        event_conf=event_conf,
        db_event=db_event,
        guild_id=guild_id,
    )

    container_items: list[discord.ui.Item] = []
    lobby_mode = bool(event_conf.get("lobby_mode"))

    # Title & Capacity Warning
    desc = event_conf.get("description", "")
    if roster_data.is_full and not (lobby_mode and event_conf.get("start_time")):
        full_label = t("EMBED_FULL", guild_id=guild_id) or "EVENT FULL"
        desc = f"### {WARNING} {full_label}\n{desc}"

    status_cfg = roster_data.computed_status
    title_prefix = ""
    if status_cfg == EventStatus.CANCELLED:
        title_prefix = f"[{t('TAG_CANCELLED', guild_id=guild_id) or 'CANCELLED'}]"
    elif status_cfg == EventStatus.POSTPONED:
        title_prefix = f"[{t('TAG_POSTPONED', guild_id=guild_id) or 'POSTPONED'}]"
    elif status_cfg == EventStatus.DELETED:
        title_prefix = f"[{t('TAG_DELETED', guild_id=guild_id) or 'DELETED'}]"
    elif status_cfg == EventStatus.RESCHEDULED:
        title_prefix = f"[{t('TAG_RESCHEDULED', guild_id=guild_id) or 'RESCHEDULED'}]"
    elif status_cfg == EventStatus.LOBBY_EXPIRED:
        title_prefix = f"[{t('TAG_LOBBY_EXPIRED', guild_id=guild_id)}]"
    elif status_cfg == EventStatus.CLOSED:
        title_prefix = f"[{t('TAG_CLOSED', guild_id=guild_id) or 'CLOSED'}]"

    title_str = ""
    if title_prefix:
        title_str += f"### **{title_prefix}**\n"

    raw_title = event_conf.get('title', t('LBL_EVENT', guild_id=guild_id))
    title_str += f"## {raw_title}"
    container_items.append(discord.ui.TextDisplay(title_str))

    if desc:
        container_items.append(discord.ui.TextDisplay(desc))

    # Time display
    start_ts_raw = event_conf.get("start_time") or (
        db_event["start_time"] if db_event and db_event.get("start_time") else None
    )
    end_ts_raw = event_conf.get("end_time") or (
        db_event["end_time"] if db_event and db_event.get("end_time") else None
    )

    time_str = ""
    meta_parts: list[str] = []

    if lobby_mode:
        if start_ts_raw is None and status_cfg == "active":
            cap_disp = int(roster_data.lobby_cap) if roster_data.lobby_cap else "?"
            time_str = t("EMBED_LOBBY_FILL", guild_id=guild_id, cap=cap_disp)
            exp = event_conf.get("lobby_expires_at")
            if exp:
                time_str += "\n" + t(
                    "EMBED_LOBBY_EXPIRES_FROM_PUBLISH",
                    guild_id=guild_id,
                    ts=int(float(exp)),
                )
        elif start_ts_raw is not None:
            start_ts = int(float(start_ts_raw))
            time_str = f"**{t('EMBED_START_TIME', guild_id=guild_id)}:** <t:{start_ts}:F>"

            if end_ts_raw and int(float(end_ts_raw)) != start_ts:
                end_ts = int(float(end_ts_raw))
                s_date = datetime.datetime.fromtimestamp(start_ts).date()
                e_date = datetime.datetime.fromtimestamp(end_ts).date()
                if s_date == e_date:
                    time_str += f" - <t:{end_ts}:t>"
                else:
                    end_label = t("EMBED_END_TIME", guild_id=guild_id)
                    time_str += f"\n**{end_label}:** <t:{end_ts}:F>"

            time_str += f"\n*{t('EMBED_LOBBY_STARTED', guild_id=guild_id)}*"
            meta_parts.append(f"{COUNTDOWN} <t:{start_ts}:R>")
        else:
            time_str = t("EMBED_LOBBY_EXPIRED_BODY", guild_id=guild_id)
    else:
        start_ts = int(float(start_ts_raw or time.time()))
        time_str = f"**{t('EMBED_START_TIME', guild_id=guild_id)}:** <t:{start_ts}:F>"

        if end_ts_raw and int(float(end_ts_raw)) != start_ts:
            end_ts = int(float(end_ts_raw))
            s_date = datetime.datetime.fromtimestamp(start_ts).date()
            e_date = datetime.datetime.fromtimestamp(end_ts).date()
            if s_date == e_date:
                time_str += f" - <t:{end_ts}:t>"
            else:
                end_label = t("EMBED_END_TIME", guild_id=guild_id)
                time_str += f"\n**{end_label}:** <t:{end_ts}:F>"

        meta_parts.append(f"{COUNTDOWN} <t:{start_ts}:R>")

        recurrence = event_conf.get("recurrence_type", "none")
        if recurrence != "none":
            rec_text = t(f"SEL_REC_{recurrence.upper()}", guild_id=guild_id) or recurrence.capitalize()
            meta_parts.append(f"{t('EMBED_RECURRENCE', guild_id=guild_id)}: {rec_text}")

    if meta_parts:
        time_str += f"\n{' • '.join(meta_parts)}"

    container_items.append(discord.ui.TextDisplay(time_str))

    # Role rosters
    container_items.append(discord.ui.Separator())
    if roster_data.role_sections:
        container_items.append(discord.ui.TextDisplay("\n\n".join(roster_data.role_sections) + "\n\n"))

    # Waiting list
    if roster_data.waiting_list:
        container_items.append(discord.ui.Separator())
        wait_header = t('EMBED_WAITLIST', guild_id=guild_id)
        wait_str = ", ".join(roster_data.waiting_list)
        container_items.append(discord.ui.TextDisplay(f"**{wait_header} ({len(roster_data.waiting_list)}):**\n{wait_str}"))

    # Images / Gallery
    image_url = None
    extra_dto = parse_extra_data(db_event.get("extra_data")) if db_event else None
    if extra_dto and extra_dto.selected_image_url:
        image_url = extra_dto.selected_image_url
    elif event_conf.get("selected_image_url"):
        image_url = event_conf.get("selected_image_url")
    else:
        db_urls = db_event.get("image_urls") if db_event else None
        conf_urls = event_conf.get("image_urls")
        target_urls = db_urls or conf_urls
        if target_urls:
            url_list = (
                [u.strip() for u in target_urls.split(",") if u.strip()]
                if isinstance(target_urls, str)
                else [u.strip() for u in target_urls if u and isinstance(u, str)]
            )
            if len(url_list) == 1:
                image_url = url_list[0]
            elif url_list:
                # Deterministic selection based on event_id:
                # Persists the chosen image across all button clicks/RSVP actions for this event instance,
                # while rotating randomly when a new recurring event instance is spawned with a new UUID.
                seed = event_id or (db_event.get("event_id") if db_event else None)
                if seed:
                    image_url = random.Random(str(seed)).choice(url_list)
                else:
                    image_url = random.choice(url_list)

    if image_url:
        try:
            from discord.ui.media_gallery import MediaGalleryItem
            container_items.append(discord.ui.MediaGallery(MediaGalleryItem(media=image_url)))
        except Exception:
            container_items.append(discord.ui.Thumbnail(media=image_url))

    # Footer & Calendar links
    creator_text = t("LBL_SYSTEM", guild_id=guild_id)
    cid = event_conf.get("creator_id")
    if cid and str(cid).isdigit():
        user = bot.get_user(int(cid))
        if user:
            creator_text = f"@{user.display_name}"
    elif cid:
        creator_text = str(cid)

    footer_text = t("EMBED_FOOTER", guild_id=guild_id, event_id=event_id, creator_id=creator_text)

    cal_title = event_conf.get("title") or (db_event.get("title") if db_event else t("LBL_EVENT", guild_id=guild_id))
    cal_desc = event_conf.get("description") or (db_event.get("description") if db_event else "")
    cal_start_raw = event_conf.get("start_time") or (db_event.get("start_time") if db_event else None)
    cal_end_ts = event_conf.get("end_time") or (db_event.get("end_time") if db_event else None)

    if lobby_mode and cal_start_raw is None:
        cal_suffix = t("EMBED_LOBBY_NO_CAL_LINKS", guild_id=guild_id)
    else:
        cal_start_ts = float(cal_start_raw) if cal_start_raw is not None else time.time()
        google_url = get_google_calendar_url(cal_title, cal_desc, cal_start_ts, cal_end_ts)
        outlook_url = get_outlook_calendar_url(cal_title, cal_desc, cal_start_ts, cal_end_ts)
        yahoo_url = get_yahoo_calendar_url(cal_title, cal_desc, cal_start_ts, cal_end_ts)
        cal_suffix = f"[Gmail]({google_url}) │ [Yahoo]({yahoo_url}) │ [Outlook]({outlook_url})"

    container_items.append(discord.ui.TextDisplay(f"-# {footer_text} • {cal_suffix}"))

    # Accent color
    status_for_color = status_cfg
    if status_for_color == EventStatus.CANCELLED:
        accent_hex = "0xE03B42"
    elif status_for_color == EventStatus.POSTPONED:
        accent_hex = "0xFEE75C"
    elif status_for_color in (EventStatus.DELETED, EventStatus.CLOSED, EventStatus.LOBBY_EXPIRED):
        accent_hex = "0x95a5a6"
    elif status_for_color == EventStatus.RESCHEDULED:
        accent_hex = "0x1FAD5E"
    else:
        accent_hex = str(event_conf.get("color") or "0x40C4FF")

    accent_color = int(accent_hex.replace("0x", "").replace("#", ""), 16)
    return discord.ui.Container(*container_items, accent_color=accent_color)

def build_card_buttons(view, event_id: str, event_conf: dict, db_event: Optional[dict], active_set: dict, rsvps: list) -> list[discord.ui.ActionRow]:
    """Generates the interactive RSVP and management button rows for the event card."""
    guild_id = event_conf.get("guild_id")
    per_row = active_set.get("buttons_per_row", 5)
    options = active_set.get("options", [])
    rows = []
    current_row_items = []
    added_count = 0

    role_limits = ParticipantFormatter.extract_role_limits(event_conf, db_event)

    for opt in options:
        if added_count >= 40:
            break
        role_id = opt.get("id")
        if not role_id:
            continue

        if role_id in role_limits:
            opt["max_slots"] = role_limits[role_id]

        label = opt.get("label") if "label" in opt else ""
        if "label_key" in opt:
            label = t(opt["label_key"], guild_id=guild_id, use_template_lang=True)
        elif role_id in ["accepted", "declined", "tentative"]:
            label_key = f"BTN_{role_id.upper()}"
            localized_label = t(label_key, guild_id=guild_id, use_template_lang=True)
            if localized_label != label_key:
                label = localized_label

        btn_style = opt.get("button_style", "both")
        btn_emoji = opt.get("emoji") if btn_style in ["both", "emoji"] else None
        btn_label = label if btn_style in ["both", "label"] else None

        color_map = {
            "success": discord.ButtonStyle.green,
            "danger": discord.ButtonStyle.red,
            "primary": discord.ButtonStyle.primary,
            "secondary": discord.ButtonStyle.secondary
        }
        btn_color = color_map.get(opt.get("button_color"), discord.ButtonStyle.secondary)

        btn = make_button(
            style=btn_color,
            emoji=to_emoji(btn_emoji) or None,
            label=btn_label or None,
            custom_id=f"{role_id}_{event_id}"
        )

        def create_callback(status_id):
            async def callback(interaction: discord.Interaction):
                await view.handle_rsvp(interaction, status_id)
            return callback

        btn.callback = create_callback(role_id)
        current_row_items.append(btn)
        added_count += 1

        if len(current_row_items) >= per_row:
            rows.append(discord.ui.ActionRow(*current_row_items))
            current_row_items = []

    status = event_conf.get("status", "active") if event_conf else db_event.get("status", "active") if db_event else "active"
    lobby_mode = bool(event_conf.get("lobby_mode"))

    if status == "postponed":
        if current_row_items:
            rows.append(discord.ui.ActionRow(*current_row_items))
        if active_set.get("show_mgmt", True) and added_count < 40:
            mgmt_items = []
            if not (lobby_mode and not event_conf.get("start_time")):
                resched_btn = make_button(label=t("BTN_RESCHEDULE", guild_id=guild_id), style=discord.ButtonStyle.primary, custom_id=f"resched_{event_id}")
                resched_btn.callback = view.reschedule_callback
                mgmt_items.append(resched_btn)
            cancel_btn = make_button(label=t("BTN_CANCEL_EVENT", guild_id=guild_id) or "Cancel", style=discord.ButtonStyle.secondary, custom_id=f"cancel_{event_id}", emoji=None)
            cancel_btn.callback = view.cancel_callback
            mgmt_items.append(cancel_btn)

            rows.append(discord.ui.ActionRow(*mgmt_items))
    else:
        if active_set.get("show_mgmt", True) and added_count < 40:
            mgmt_items = []

            if not (lobby_mode and not event_conf.get("start_time")):
                postpone_btn = make_button(label=t("BTN_POSTPONE_EVENT", guild_id=guild_id) or "Postpone", style=discord.ButtonStyle.secondary, custom_id=f"postpone_{event_id}", emoji=None)
                postpone_btn.callback = view.postpone_callback
                mgmt_items.append(postpone_btn)

            cancel_btn = make_button(label=t("BTN_CANCEL_EVENT", guild_id=guild_id) or "Cancel", style=discord.ButtonStyle.secondary, custom_id=f"cancel_{event_id}", emoji=None)
            cancel_btn.callback = view.cancel_callback
            mgmt_items.append(cancel_btn)

            if len(current_row_items) + len(mgmt_items) <= 5:
                current_row_items.extend(mgmt_items)
                if current_row_items:
                    rows.append(discord.ui.ActionRow(*current_row_items))
            else:
                if current_row_items:
                    rows.append(discord.ui.ActionRow(*current_row_items))
                rows.append(discord.ui.ActionRow(*mgmt_items))
        else:
            if current_row_items:
                rows.append(discord.ui.ActionRow(*current_row_items))

    return rows

def update_button_states(view, rsvps_list: list, event_conf: dict, active_set: dict, ui_status: Optional[str] = None):
    """Disables buttons if capacity limits are reached or if the event status is inactive."""
    status = ui_status or event_conf.get("status", "active")

    all_buttons = []
    for child in view.children:
        if isinstance(child, discord.ui.Container):
            for row in child.children:
                if isinstance(row, discord.ui.ActionRow):
                    for item in row.children:
                        if isinstance(item, discord.ui.Button):
                            all_buttons.append(item)
                elif isinstance(row, discord.ui.Button):
                    all_buttons.append(row)
        elif isinstance(child, discord.ui.ActionRow):
            for item in child.children:
                if isinstance(item, discord.ui.Button):
                    all_buttons.append(item)
        elif isinstance(child, discord.ui.Button):
            all_buttons.append(child)

    if status in (EventStatus.CANCELLED, EventStatus.POSTPONED, EventStatus.DELETED, EventStatus.LOBBY_EXPIRED, EventStatus.CLOSED):
        for btn in all_buttons:
            allowed_prefix = ("edit_", "delete_", "calendar_", "resched_")
            if status == EventStatus.POSTPONED:
                allowed_prefix += ("cancel_",)
            if not btn.custom_id.startswith(allowed_prefix):
                btn.disabled = True
        return

    use_waiting = event_conf.get("use_waiting_list", True)
    if use_waiting:
        for btn in all_buttons:
            if btn.custom_id and "_" in btn.custom_id and not btn.custom_id.startswith(("edit_", "delete_", "calendar_")):
                btn.disabled = False
        return

    # Use ParticipantFormatter to compute capacity and status counts
    roster_data = ParticipantFormatter.format_roster(active_set, rsvps_list, event_conf)

    for btn in all_buttons:
        if not btn.custom_id:
            continue
        if btn.custom_id.startswith(("edit_", "delete_", "calendar_")):
            continue

        parts = btn.custom_id.split("_")
        if len(parts) < 2:
            continue
        role_id = "_".join(parts[:-1])

        btn.disabled = False

        if role_id in roster_data.positive_statuses and roster_data.eff_event_cap > 0:
            if roster_data.total_positive_count >= roster_data.eff_event_cap:
                btn.disabled = True

        role_limit = roster_data.role_limits.get(role_id)
        if role_limit is None:
            opt = next((o for o in active_set.get("options", []) if o["id"] == role_id), None)
            if opt:
                role_limit = opt.get("max_slots")

        if role_limit and role_limit > 0:
            curr_role_count = roster_data.status_counts.get(role_id, 0)
            if curr_role_count >= role_limit:
                btn.disabled = True
