import time
import json
import asyncio
import discord
import database
from utils.i18n import t
from utils.logger import log
from utils.emoji_utils import resolve_placeholders
from .notifications import notify_promotion
from .lobby import process_lobby_transition

# Cooldown cache for RSVP button presses (only enforced when waiting list is active)
# Key: (event_id, user_id) -> timestamp of last RSVP change
_rsvp_cooldowns: dict[tuple, float] = {}
RSVP_COOLDOWN_SECONDS = 60

async def try_promote_waiting(bot, event_id: str, event_conf: dict, active_set: dict, interaction: discord.Interaction, db_event: dict, role_limits: dict, rsvps=None):
    """Attempts to promote the earliest waiting user across all eligible roles."""
    if rsvps is None:
        rsvps_raw = await database.get_rsvps_with_time(event_id)
        rsvps = [dict(r) for r in rsvps_raw]
    
    positive_statuses = [o["id"] for o in active_set["options"] if o.get("positive")]
    if not positive_statuses and "positive_count" in active_set:
        cnt = active_set["positive_count"]
        positive_statuses = [o["id"] for o in active_set["options"][:cnt]]
        
    max_acc = event_conf.get('max_accepted', 0)
    
    # Sort by joined_at to ensure FIFO fairness (earliest first)
    waiting = sorted([r for r in rsvps if str(r["status"]).startswith("wait_")], key=lambda x: x["joined_at"])
    if not waiting:
        return

    for w in waiting:
        current_acc = sum(1 for r in rsvps if r["status"] in positive_statuses)
        if max_acc > 0 and current_acc >= max_acc:
            break
            
        wait_status = str(w["status"])
        target_status = wait_status.replace("wait_", "")
        
        # Check role-specific limit
        role_limit = role_limits.get(target_status)
        if role_limit is None:
            opt = next((o for o in active_set.get("options", []) if o["id"] == target_status), None)
            if opt:
                role_limit = opt.get("max_slots")
        
        if role_limit and sum(1 for r in rsvps if r["status"] == target_status) >= role_limit:
            continue
            
        # Promotion found
        user_id = w["user_id"]
        await database.update_rsvp(event_id, user_id, target_status)
        
        opt = next((o for o in active_set["options"] if o["id"] == target_status), None)
        if opt:
            await notify_promotion(bot, interaction, event_id, event_conf, user_id, opt)
            
        log.info(f"[Promotion] User {user_id} promoted to {target_status} for event {event_id}")
        
        for r in rsvps:
            if r["user_id"] == user_id:
                r["status"] = target_status
                break

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
        last_press = _rsvp_cooldowns.get(cd_key, 0)
        elapsed = time.time() - last_press
        if elapsed < RSVP_COOLDOWN_SECONDS:
            remaining = int(RSVP_COOLDOWN_SECONDS - elapsed)
            return await interaction.response.send_message(
                t("ERR_RSVP_COOLDOWN", guild_id=interaction.guild_id, seconds=remaining),
                ephemeral=True,
            )
        _rsvp_cooldowns[cd_key] = time.time()

    gid_chk = interaction.guild_id or db_event.get("guild_id")
    if db_event.get("status") == "lobby_expired":
        return await interaction.response.send_message(
            t("ERR_LOBBY_EXPIRED", guild_id=gid_chk), ephemeral=True
        )
    if (
        db_event.get("lobby_mode")
        and db_event.get("status") == "active"
        and db_event.get("start_time") is None
    ):
        exp = db_event.get("lobby_expires_at")
        if exp is not None and time.time() > float(exp):
            return await interaction.response.send_message(
                t("ERR_LOBBY_EXPIRED", guild_id=gid_chk), ephemeral=True
            )
    if db_event["status"] not in ["active", "rescheduled"]:
        return await interaction.response.send_message(t("ERR_EV_INACTIVE"), ephemeral=True)

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
        user_role_ids = {str(r.id) for r in interaction.user.roles}
        if not any(rid in user_role_ids for rid in allowed_ids):
            return await interaction.response.send_message(
                t("ERR_RSVP_ROLE_REQUIRED", guild_id=interaction.guild_id),
                ephemeral=True,
            )

    if not view.event_conf:
        from .config import get_event_conf
        view.event_conf = get_event_conf(db_event["config_name"])
        if not view.event_conf:
            view.event_conf = dict(db_event)
            ex = db_event.get("extra_data")
            if ex:
                try:
                    d = json.loads(ex) if isinstance(ex, str) else ex
                    if isinstance(d, dict):
                        view.event_conf.update(d)
                except Exception as e:
                    log.debug("handle_rsvp extra_data: %s", e)
    
    rsvps_raw = await database.get_rsvps_with_time(event_id)
    rsvps_list = [dict(r) for r in rsvps_raw]

    old_status = next((s["status"] for s in rsvps_list if s["user_id"] == interaction.user.id), None)
    target_status, opt = status, next((o for o in active_set["options"] if o["id"] == status), None)
    
    ex = db_event.get("extra_data")
    role_limits = {}
    if ex:
        try:
            d = json.loads(ex) if isinstance(ex, str) else ex
            role_limits = d.get("role_limits", {})
        except Exception as e:
            log.debug("handle_rsvp role_limits: %s", e)
        
    role_limit = role_limits.get(status, opt.get("max_slots") if opt else None)
    if role_limit and sum(1 for s in rsvps_list if s["status"] == status) >= role_limit and old_status != status:
        if view.event_conf.get("use_waiting_list", True): 
            # Global waitlist limit check
            wait_limit = role_limits.get("waiting_list_limit", 0)
            if wait_limit > 0:
                wait_count = sum(1 for s in rsvps_list if str(s["status"]).startswith("wait_"))
                if wait_count >= wait_limit and not str(old_status).startswith("wait_"):
                    return await interaction.response.send_message(t("ERR_WAITLIST_FULL", guild_id=interaction.guild_id), ephemeral=True)
            
            target_status = f"wait_{status}"
            try:
                hint = t("MSG_WAITLIST_HINT", guild_id=interaction.guild_id, user_id=interaction.user.id, role=(opt.get('label') or status))
                hint = resolve_placeholders(hint)
                await interaction.user.send(hint)
            except Exception as e:
                log.debug("waitlist hint DM: %s", e)
        else:
            return await interaction.response.send_message(t("ERR_POS_FULL", guild_id=interaction.guild_id, name=(opt.get('label') or opt['id'])), ephemeral=True)

    positive_statuses = active_set.get("positive", [])
    if not positive_statuses and "positive_count" in active_set:
        cnt = active_set["positive_count"]
        positive_statuses = [o["id"] for o in active_set["options"][:cnt]]

    if target_status in positive_statuses:
        max_acc = view.event_conf.get('max_accepted', 0)
        if max_acc > 0 and sum(1 for s in rsvps_list if s["status"] in positive_statuses) >= max_acc and old_status not in positive_statuses:
            if not target_status.startswith("wait_"): 
                target_status = f"wait_{status}"
                try:
                    hint = t("MSG_WAITLIST_HINT", guild_id=interaction.guild_id, user_id=interaction.user.id, role=(opt.get('label') or status))
                    hint = resolve_placeholders(hint)
                    await interaction.user.send(hint)
                except Exception as e:
                    log.debug("waitlist hint DM (event cap): %s", e)

    await interaction.response.defer()
    await database.update_rsvp(event_id, interaction.user.id, target_status)
    
    # Update local state immediately
    found = False
    for r in rsvps_list:
        if r["user_id"] == interaction.user.id:
            r["status"] = target_status
            r["joined_at"] = time.time()
            found = True
            break
    if not found:
        rsvps_list.append({"user_id": interaction.user.id, "status": target_status, "joined_at": time.time()})

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
        await try_promote_waiting(bot, event_id, view.event_conf, active_set, interaction, db_event, role_limits, rsvps=rsvps_list)
    elif was_positive and still_positive and old_status != target_status:
        await try_promote_waiting(bot, event_id, view.event_conf, active_set, interaction, db_event, role_limits, rsvps=rsvps_list)

    gid_raw = interaction.guild_id or db_event.get("guild_id")
    if db_event.get("lobby_mode") and gid_raw:
        await process_lobby_transition(bot, event_id, active_set, int(str(gid_raw)))

    await asyncio.sleep(0.12)
    
    # Fresh view recreation pattern
    try:
        from .views.dynamic_card import DynamicEventView
        new_view = DynamicEventView(bot, event_id, view.event_conf)
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
