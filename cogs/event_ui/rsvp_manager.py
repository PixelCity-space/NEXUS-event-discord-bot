import time
import discord
import database
from utils.i18n import t
from utils.logger import log
from utils.enums import EventStatus
from utils.emoji_utils import resolve_placeholders
from utils.cache import cooldown_cache
from utils.extra_data import parse_extra_data
from .notifications import notify_promotion
from .lobby import process_lobby_transition

# Cooldown cache for RSVP button presses (bounded TTL cache preventing memory leaks)
_rsvp_cooldowns = cooldown_cache
RSVP_COOLDOWN_SECONDS = 60

async def try_promote_waiting(bot, event_id: str, event_conf: dict, active_set: dict, interaction: discord.Interaction, db_event: dict, role_limits: dict, rsvps=None):
    """Attempts to promote the earliest waiting user across all eligible roles atomically."""
    positive_statuses = [o["id"] for o in active_set["options"] if o.get("positive")]
    if not positive_statuses and "positive_count" in active_set:
        cnt = active_set["positive_count"]
        positive_statuses = [o["id"] for o in active_set["options"][:cnt]]

    max_acc = int(event_conf.get("max_accepted", 0) or 0)

    # Merge active_set option limits with role_limits
    merged_limits = dict(role_limits or {})
    for opt in active_set.get("options", []):
        oid = opt.get("id")
        if oid and oid not in merged_limits and opt.get("max_slots"):
            merged_limits[oid] = opt["max_slots"]

    # Execute atomic row-level locked promotion
    promoted_users = await database.promote_waiting_users_atomic(
        event_id=event_id,
        positive_statuses=positive_statuses,
        max_accepted=max_acc,
        role_limits=merged_limits,
    )

    if promoted_users:
        # Notify newly promoted users
        for promoted in promoted_users:
            if isinstance(promoted, (tuple, list)):
                promoted_uid, promoted_role = int(promoted[0]), str(promoted[1])
            elif isinstance(promoted, dict):
                promoted_uid, promoted_role = int(promoted["user_id"]), str(promoted["target_role"])
            else:
                continue

            opt = next((o for o in active_set["options"] if o["id"] == promoted_role), None)
            if opt:
                try:
                    await notify_promotion(bot, interaction, event_id, event_conf, promoted_uid, opt)
                except Exception as e:
                    log.error(f"[RSVP] Failed to send promotion notification to {promoted_uid}: {e}")

            log.info(f"[Promotion] User {promoted_uid} promoted to {promoted_role} for event {event_id}")

            if rsvps is not None:
                for r in rsvps:
                    if r["user_id"] == promoted_uid:
                        r["status"] = promoted_role
                        break

            # Assign temporary Discord role if configured
            if db_event.get("use_temp_role") and db_event.get("temp_role_id") and interaction.guild:
                try:
                    role = interaction.guild.get_role(int(db_event["temp_role_id"]))
                    promoted_member = interaction.guild.get_member(promoted_uid)
                    if not promoted_member:
                        try:
                            promoted_member = await interaction.guild.fetch_member(promoted_uid)
                        except Exception:
                            pass
                    if role and promoted_member and role not in promoted_member.roles:
                        await promoted_member.add_roles(role, reason=f"RSVP Auto-Promoted: {event_id}")
                        log.info(f"[RSVP] Assigned role {db_event['temp_role_id']} to auto-promoted {promoted_uid}")
                except Exception as e:
                    log.error(f"[RSVP] Auto-promotion role management error: {e}")

async def handle_rsvp(view, interaction: discord.Interaction, status: str):
    """Processes user RSVP click, enforcing limits, roles, waitlist queues, and temp roles."""
    event_id = view.event_id
    bot = view.bot
    active_set = view.active_set

    db_event = await database.get_active_event(event_id)
    if not db_event:
        return await interaction.response.send_message(t("ERR_EV_NOT_FOUND"), ephemeral=True)

    # Cooldown check: only enforce when waiting list is explicitly enabled
    has_waitlist = db_event.get("use_waiting_list", False)
    if has_waitlist:
        cd_key = (event_id, interaction.user.id)
        last_press = _rsvp_cooldowns.get(cd_key, 0.0)
        elapsed = time.time() - last_press
        if elapsed < RSVP_COOLDOWN_SECONDS:
            remaining = int(RSVP_COOLDOWN_SECONDS - elapsed)
            return await interaction.response.send_message(
                t("ERR_RSVP_COOLDOWN", guild_id=interaction.guild_id, seconds=remaining),
                ephemeral=True,
            )
        _rsvp_cooldowns[cd_key] = time.time()

    gid_chk = interaction.guild_id or db_event.get("guild_id")
    ev_status = db_event.get("status")
    if ev_status == EventStatus.LOBBY_EXPIRED:
        return await interaction.response.send_message(
            t("ERR_LOBBY_EXPIRED", guild_id=gid_chk), ephemeral=True
        )
    if (
        db_event.get("lobby_mode")
        and ev_status == EventStatus.ACTIVE
        and db_event.get("start_time") is None
    ):
        exp = db_event.get("lobby_expires_at")
        if exp is not None and time.time() > float(exp):
            return await interaction.response.send_message(
                t("ERR_LOBBY_EXPIRED", guild_id=gid_chk), ephemeral=True
            )
    if ev_status not in (EventStatus.ACTIVE, EventStatus.RESCHEDULED):
        return await interaction.response.send_message(t("ERR_EV_INACTIVE"), ephemeral=True)

    # Check allowed RSVP roles
    raw_allowed = db_event.get("rsvp_allowed_role_ids")
    if raw_allowed:
        allowed_ids = [x.strip() for x in str(raw_allowed).split(",") if x.strip().isdigit()]
    else:
        allowed_ids = []
    if allowed_ids:
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(
                t("ERR_RSVP_NEED_SERVER", guild_id=interaction.guild_id),
                ephemeral=True,
            )
        user_role_ids = {str(r.id) for r in getattr(interaction.user, "roles", [])}
        if not any(rid in user_role_ids for rid in allowed_ids):
            return await interaction.response.send_message(
                t("ERR_RSVP_ROLE_REQUIRED", guild_id=interaction.guild_id),
                ephemeral=True,
            )

    extra_dto = parse_extra_data(db_event.get("extra_data"))
    if not view.event_conf:
        from .config import get_event_conf
        view.event_conf = get_event_conf(db_event.get("config_name"))
        if not view.event_conf:
            view.event_conf = dict(db_event)
            view.event_conf.update(extra_dto.to_dict())
    
    role_limits = dict(extra_dto.role_limits)
    opt = next((o for o in active_set["options"] if o["id"] == status), None)
    if opt and opt.get("max_slots") and status not in role_limits:
        role_limits[status] = opt["max_slots"]

    positive_statuses = active_set.get("positive", [])
    if not positive_statuses and "positive_count" in active_set:
        cnt = active_set["positive_count"]
        positive_statuses = [o["id"] for o in active_set["options"][:cnt]]

    max_acc = int(view.event_conf.get('max_accepted', 0) or 0)
    use_waitlist = bool(view.event_conf.get("use_waiting_list", True))
    wait_limit = int(extra_dto.waiting_list_limit or role_limits.get("waiting_list_limit", 0) or 0)

    # Atomic evaluation and reservation under PostgreSQL row lock
    result = await database.join_or_update_rsvp_atomic(
        event_id=event_id,
        user_id=interaction.user.id,
        status=status,
        positive_statuses=positive_statuses,
        max_accepted=max_acc,
        role_limits=role_limits,
        use_waiting_list=use_waitlist,
        waiting_list_limit=wait_limit,
    )

    if result.get("is_full"):
        err_type = result.get("error")
        if err_type == "waitlist_full":
            return await interaction.response.send_message(
                t("ERR_WAITLIST_FULL", guild_id=interaction.guild_id), ephemeral=True
            )
        else:
            opt_name = (opt.get('label') or opt.get('id', status)) if opt else status
            return await interaction.response.send_message(
                t("ERR_POS_FULL", guild_id=interaction.guild_id, name=opt_name), ephemeral=True
            )

    target_status = result["target_status"]
    old_status = result["old_status"]

    if result.get("is_waitlist"):
        try:
            hint = t("MSG_WAITLIST_HINT", guild_id=interaction.guild_id, user_id=interaction.user.id, role=(opt.get('label') or status))
            hint = resolve_placeholders(hint)
            await interaction.user.send(hint)
        except Exception as e:
            log.debug("waitlist hint DM: %s", e)

    await interaction.response.defer()

    # Temp Role Management
    temp_role_id = db_event.get("temp_role_id")
    if temp_role_id and isinstance(interaction.user, discord.Member):
        if not interaction.guild.me.guild_permissions.manage_roles:
            log.warning(f"[RSVP] Missing 'Manage Roles' permission to handle temp role {temp_role_id} in guild {interaction.guild_id}")
        else:
            role = interaction.guild.get_role(int(temp_role_id))
            if role:
                try:
                    if target_status in positive_statuses:
                        if role not in interaction.user.roles:
                            await interaction.user.add_roles(role, reason=f"RSVP positive: {event_id}")
                            log.info(f"[RSVP] Added role {temp_role_id} to {interaction.user.id} for event {event_id}")
                    else:
                        if role in interaction.user.roles:
                            await interaction.user.remove_roles(role, reason=f"RSVP negative/left: {event_id}")
                            log.info(f"[RSVP] Removed role {temp_role_id} from {interaction.user.id} for event {event_id}")
                except Exception as e:
                    log.error(f"[RSVP] Role management error: {e}")

    # Check for promotions if a slot was vacated
    was_positive = old_status in positive_statuses
    still_positive = target_status in positive_statuses
    if was_positive and not still_positive:
        await try_promote_waiting(bot, event_id, view.event_conf, active_set, interaction, db_event, role_limits)
    elif was_positive and still_positive and old_status != target_status:
        await try_promote_waiting(bot, event_id, view.event_conf, active_set, interaction, db_event, role_limits)

    gid_raw = interaction.guild_id or db_event.get("guild_id")
    if db_event.get("lobby_mode") and gid_raw:
        await process_lobby_transition(bot, event_id, active_set, int(str(gid_raw)))

    # Deterministic fresh view recreation and immediate response (no magic sleep)
    try:
        new_view = view.__class__(bot, event_id, view.event_conf)
        await new_view.prepare()

        if not interaction.response.is_done():
            await interaction.response.edit_message(content=None, embeds=[], view=new_view)
        else:
            await interaction.edit_original_response(content=None, embeds=[], view=new_view)
    except Exception as e:
        log.debug(f"Refresh handling error: {e}")
        try:
            await interaction.followup.edit_message(message_id="@original", view=view)
        except Exception:
            pass
    log.info(f"User {interaction.user} RSVP'd {status} for event {event_id}", guild_id=interaction.guild_id)
