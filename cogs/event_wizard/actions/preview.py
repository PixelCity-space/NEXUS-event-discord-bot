import uuid
import json
import datetime
import discord
from dateutil import parser, tz
from database import DEFAULT_TIMEZONE
from utils.i18n import t
from utils.logger import log

async def process_save_preview(wizard_view, interaction: discord.Interaction):
    """Processes the Save & Preview logic and renders the preview card."""
    if wizard_view.wizard_type in ("single", "lobby"):
        if not wizard_view.steps_completed["step1"]:
            await interaction.response.send_message(t("ERR_FILL_STEP1", guild_id=wizard_view.guild_id), ephemeral=True)
            return
    else:
        if not wizard_view.steps_completed["step1"] or not wizard_view.steps_completed["step2"]:
            await interaction.response.send_message(t("ERR_FILL_STEPS_1_2", guild_id=wizard_view.guild_id), ephemeral=True)
            return
        
    if wizard_view.wizard_type == "series":
        rtype = wizard_view.data.get("recurrence_type")
        if rtype == "custom" and not wizard_view.data.get("custom_days"):
            await interaction.response.send_message(t("ERR_FILL_CUSTOM_DAYS", guild_id=wizard_view.guild_id), ephemeral=True)
            return
        if rtype == "relative":
            rel_combo = wizard_view.data.get("relative_combo", [])
            if len(rel_combo) != 2:
                await interaction.response.send_message(t("ERR_FILL_RELATIVE", guild_id=wizard_view.guild_id), ephemeral=True)
                return
            # Ensure they picked 1 week and 1 day
            has_wk = any(c.startswith("wk_") for c in rel_combo)
            has_day = any(c.startswith("day_") for c in rel_combo)
            if not (has_wk and has_day):
                await interaction.response.send_message(t("ERR_FILL_RELATIVE_MIX", guild_id=wizard_view.guild_id), ephemeral=True)
                return

    clean_data = {}
    for k, v in wizard_view.data.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            clean_data[k] = v
        elif isinstance(v, list):
            clean_data[k] = ",".join(str(i) for i in v)
        else:
            clean_data[k] = str(v)
    wizard_view.data = clean_data

    if wizard_view.wizard_type == "lobby":
        wizard_view.data["lobby_mode"] = True
        wizard_view.data["start_time"] = None
        wizard_view.data["end_time"] = None
        wizard_view.data["use_waiting_list"] = False
        wizard_view.data["reminder_offsets"] = []
        
        from cogs.event_ui import get_active_set
        from utils.lobby_utils import effective_lobby_capacity, role_limits_from_extra

        active_set = get_active_set(wizard_view.data.get("icon_set", "standard"))
        rl = role_limits_from_extra(wizard_view.data.get("extra_data"))
        cap = effective_lobby_capacity(int(wizard_view.data.get("max_accepted") or 0), active_set, rl)
        if cap is None:
            await interaction.response.send_message(
                t("ERR_LOBBY_CAP_INVALID", guild_id=wizard_view.guild_id), ephemeral=True
            )
            return
    else:
        try:
            local_tz = tz.gettz(str(wizard_view.data.get("timezone") or DEFAULT_TIMEZONE))
            base_now = datetime.datetime.now(local_tz)
            
            start_dt = parser.parse(str(wizard_view.data["start_str"]), default=base_now).replace(tzinfo=local_tz)
            wizard_view.data["start_time"] = start_dt.timestamp()

            if wizard_view.data.get("end_str"):
                end_dt = parser.parse(str(wizard_view.data["end_str"]), default=start_dt).replace(tzinfo=local_tz)
                wizard_view.data["end_time"] = end_dt.timestamp()
            else:
                wizard_view.data["end_time"] = None
        except Exception as e:
            await interaction.response.send_message(
                t("ERR_DATE_TZ", guild_id=wizard_view.guild_id, e=str(e)), ephemeral=True
            )
            return

    await interaction.response.defer(ephemeral=True)
    
    try:
        from cogs.event_ui import DynamicEventView
        event_id = str(wizard_view.data.get("event_id") or str(uuid.uuid4())[:8])
        wizard_view.data["event_id"] = event_id
        
        if wizard_view.is_edit:
            if "creator_id" not in wizard_view.data:
                wizard_view.data["creator_id"] = str(wizard_view.creator_id)
        else:
            wizard_view.data["creator_id"] = str(wizard_view.data.get("creator_id") or wizard_view.creator_id)
            wizard_view.data["guild_id"] = wizard_view.guild_id
            
            target_channel_id = interaction.channel_id
            if wizard_view.data.get("channel_id") and str(wizard_view.data["channel_id"]).isdigit():
                target_channel_id = int(wizard_view.data["channel_id"])
                
            wizard_view.data["target_channel_id"] = target_channel_id

        wizard_view.can_publish = True
        
        view = DynamicEventView(wizard_view.bot, event_id, wizard_view.data, is_preview=True)
        await view.prepare()
        
        global_max = int(wizard_view.data.get("max_accepted") or 0)
        role_sum = 0
        
        from cogs.event_ui import get_active_set
        icon_set_key = wizard_view.data.get("icon_set", "standard")
        active_set = get_active_set(icon_set_key)
        
        extra_data = wizard_view.data.get("extra_data")
        role_limits_overrides = {}
        if extra_data:
            try:
                d = json.loads(extra_data) if isinstance(extra_data, str) else extra_data
                role_limits_overrides = d.get("role_limits", {})
            except Exception as e:
                log.debug("process_save_preview role_limits: %s", e)
        
        pos_statuses = []
        if "positive" in active_set:
            pos_statuses = active_set["positive"]
        elif "positive_count" in active_set:
            cnt = active_set["positive_count"]
            pos_statuses = [o["id"] for o in active_set["options"][:cnt]]
        
        for opt in active_set.get("options", []):
            rid = opt["id"]
            if rid in pos_statuses:
                limit = role_limits_overrides.get(rid, opt.get("max_slots", 0))
                role_sum += (limit or 0)
        
        warning = ""
        if global_max > 0 and role_sum > 0 and global_max != role_sum:
            warning = t(
                "WARN_ROLE_LIMIT_MISMATCH", 
                guild_id=wizard_view.guild_id, 
                role_sum=role_sum, 
                global_max=global_max, 
                default=f"\n\n**Warning:** The sum of roles (**{role_sum}**) does not match the global limit (**{global_max}**)."
            )
            if role_sum < global_max:
                warning += "\n" + t("WARN_ROLE_LIMIT_UNDER", guild_id=wizard_view.guild_id, role_sum=role_sum)
            else:
                warning += "\n" + t("WARN_ROLE_LIMIT_OVER", guild_id=wizard_view.guild_id, global_max=global_max)

        preview_text = t("MSG_SAVED_PREVIEW", guild_id=wizard_view.guild_id) + warning
        if preview_text:
            await interaction.followup.send(preview_text, ephemeral=True)
        await interaction.followup.send(view=view, ephemeral=True)
        await wizard_view.refresh_message(interaction)
    except Exception as e:
        log.error(f"Error in process_save_preview: {e}", exc_info=True)
        try:
            await interaction.followup.send(
                f"{t('ERR_CRITICAL_WIZARD', guild_id=wizard_view.guild_id)}: `{e}`",
                ephemeral=True,
            )
        except Exception as send_err:
            log.error(f"process_save_preview followup failed: {send_err}")
