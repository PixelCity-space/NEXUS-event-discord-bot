import time
import discord
import database
from utils.emojis import PING
from utils.emoji_utils import resolve_placeholders
from utils.i18n import t
from utils.logger import log
from utils.text_utils import safe_format
from utils.extra_data import parse_extra_data
from services.notification_service import resolve_target_recipients, send_event_alert

async def send_lobby_fill_notifications(bot: discord.Client, db_event: dict, active_set: dict, guild_id_int: int) -> None:
    """Sends notification when a fill-to-start lobby reaches its required capacity."""
    et = (db_event.get("reminder_type") or "").strip().lower()
    if et in ("none", ""):
        if not db_event.get("lobby_remind_on_fill", True):
            return
        et = (
            await database.get_guild_setting(guild_id_int, "reminder_type", default="none") or "none"
        ).lower()
    if et in ("none", ""):
        return

    rsvps = await database.get_rsvps(db_event["event_id"])
    target_user_ids = resolve_target_recipients(
        bot=bot,
        db_event=db_event,
        target_raw="coming",
        rsvps=rsvps,
        active_set=active_set,
    )
    if not target_user_ids:
        return

    title = db_event.get("title") or "Event"
    rem_text = t("MSG_LOBBY_FILL_DESC", guild_id=guild_id_int, title=title)
    rem_text = resolve_placeholders(rem_text)
    start_ts = int(db_event.get("start_time") or time.time())

    embed = discord.Embed(
        title=t("LBL_LOBBY_FILL_TITLE", guild_id=guild_id_int),
        description=rem_text,
        color=discord.Color.green(),
    )
    embed.add_field(
        name=t("LBL_STARTS", guild_id=guild_id_int),
        value=f"<t:{start_ts}:F>",
    )

    await send_event_alert(
        bot=bot,
        channel_id=db_event.get("channel_id"),
        target_user_ids=target_user_ids,
        method=et,
        embed=embed,
        temp_role_id=db_event.get("temp_role_id"),
    )

async def send_status_notification(bot: discord.Client, event_id: str, db_event: dict, status_name: str, guild_id: int) -> None:
    """Sends a broadcast in the channel and DMs participants about status changes."""
    rsvps = await database.get_rsvps(event_id)
    target_user_ids = resolve_target_recipients(
        bot=bot,
        db_event=db_event,
        target_raw="all",
        rsvps=rsvps,
        active_set={},
    )

    channel_id = db_event.get("channel_id")
    if not channel_id:
        return

    ping_role = db_event.get("ping_role")
    ping_prefix = ""
    if ping_role and str(ping_role).isdigit() and int(ping_role) > 0:
        ping_prefix = f"{PING} <@&{ping_role}> "

    title = db_event.get("title", "Event")
    if status_name == "cancelled":
        msg_body = t("MSG_EVENT_CANCELLED", guild_id=guild_id, title=title)
    elif status_name == "postponed":
        msg_body = t("MSG_EVENT_POSTPONED", guild_id=guild_id, title=title)
    elif status_name == "deleted":
        msg_body = f"The event ({title}) has been deleted."
    else:
        msg_body = f"Event ({title}) status updated: {status_name}"

    if msg_body:
        msg_body = resolve_placeholders(msg_body)
        content = f"{ping_prefix}{msg_body}"

    notify_type = await database.get_guild_setting(guild_id, "status_notification_type", default="none")
    notify_type = (notify_type or "none").lower()

    dm_msg = f"{PING} {msg_body}"

    await send_event_alert(
        bot=bot,
        channel_id=channel_id,
        target_user_ids=target_user_ids,
        method=notify_type,
        content=content,
        dm_content=dm_msg,
        include_target_mentions=False,
    )

async def notify_promotion(bot: discord.Client, interaction: discord.Interaction, event_id: str, event_conf: dict, user_id: int, opt: dict) -> None:
    """Sends notification to a user and channel when promoted from waitlist to active."""
    notify_type = event_conf.get("notify_promotion", "none")
    if notify_type == "none":
        return

    db_event = await database.get_active_event(event_id, interaction.guild_id)
    if not db_event:
        return

    role_name = opt.get("label") or opt.get("list_label") or opt["id"]
    extra_dto = parse_extra_data(event_conf.get("extra_data"))
    custom_msg = extra_dto.custom_promo_msg

    if custom_msg:
        msg = safe_format(custom_msg, user_id=user_id, role=role_name, emoji=opt.get("emoji", ""), title=event_conf.get("title", ""))
    else:
        msg = t("MSG_PROMOTED_DEFAULT", guild_id=interaction.guild_id, user_id=user_id, role=role_name, emoji=opt.get("emoji", ""))

    msg = resolve_placeholders(msg)

    jump_link = f"https://discord.com/channels/{interaction.guild_id}/{db_event['channel_id']}/{db_event['message_id']}"
    msg += f"\n🔗 {jump_link}"

    await send_event_alert(
        bot=bot,
        channel_id=interaction.channel_id,
        target_user_ids=[user_id],
        method=notify_type,
        content=msg,
        dm_content=msg,
        include_target_mentions=False,
    )

    # Assign temp role if configured
    if db_event.get("temp_role_id"):
        guild = interaction.guild
        if guild and guild.me.guild_permissions.manage_roles:
            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                if member:
                    role = guild.get_role(int(db_event["temp_role_id"]))
                    if role and role not in member.roles:
                        await member.add_roles(role, reason=f"Promoted to active: {event_id}")
                        log.info(f"[Promotion] Added role {db_event['temp_role_id']} to {user_id} for event {event_id}")
            except Exception as e:
                log.error(f"[Promotion] Role management error: {e}")
