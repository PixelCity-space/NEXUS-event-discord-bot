import time
import datetime
import discord
import database
from utils.emojis import PING
from utils.i18n import t
from utils.logger import log
from utils.offset_parse import parse_offset
from utils.lobby_utils import effective_lobby_capacity, role_limits_from_extra
from utils.extra_data import parse_extra_data
from cogs.event_ui import DynamicEventView, get_active_set

async def process_publish(wizard_view, interaction: discord.Interaction):
    """Handles the final publish and persistence of an event to Discord and Database."""
    await interaction.response.defer(ephemeral=True)
    event_id = wizard_view.data["event_id"]

    try:
        if wizard_view.wizard_type == "lobby":
            wizard_view.data["lobby_mode"] = True
            active_set = get_active_set(wizard_view.data.get("icon_set", "standard"))
            rl = role_limits_from_extra(wizard_view.data.get("extra_data"))
            cap = effective_lobby_capacity(int(wizard_view.data.get("max_accepted") or 0), active_set, rl)
            if cap is None:
                await interaction.followup.send(
                    t("ERR_LOBBY_CAP_INVALID", guild_id=wizard_view.guild_id), ephemeral=True
                )
                return
            off = parse_offset(str(wizard_view.data.get("lobby_expire_offset") or "12h"))
            wizard_view.data["lobby_expires_at"] = time.time() + off.total_seconds()
            wizard_view.data["start_time"] = None
            wizard_view.data["end_time"] = None
            wizard_view.data["use_waiting_list"] = False
            wizard_view.data["reminder_offsets"] = []
            wizard_view.data["lobby_remind_on_fill"] = (
                (wizard_view.data.get("reminder_type") or "none").lower() not in ("none", "")
            )

        # Temporary Role Creation Logic
        if wizard_view.data.get("use_temp_role") and not wizard_view.data.get("temp_role_id"):
            guild = wizard_view.bot.get_guild(int(wizard_view.guild_id))
            if guild:
                title = (wizard_view.data.get("title") or "Event")[:30]
                date_str = ""
                try:
                    ts = float(wizard_view.data.get("start_time") or 0)
                    if ts:
                        dt = datetime.datetime.fromtimestamp(ts)
                        date_str = dt.strftime("%m%d")
                except Exception as e:
                    log.debug("process_publish temp role date_str: %s", e)
                
                role_name = f"{title} - {date_str}" if date_str else title
                try:
                    new_role = await guild.create_role(name=role_name, mentionable=True, reason=f"Nexus Event: {event_id}")
                    wizard_view.data["temp_role_id"] = new_role.id
                    log.info(f"[Wizard] Created temp role {new_role.name} ({new_role.id}) for event {event_id}")
                except Exception as e:
                    log.error(f"[Wizard] Failed to create temp role: {e}")
        
        target_chan = interaction.channel
        if wizard_view.data.get("channel_id") and str(wizard_view.data["channel_id"]).isdigit():
            chan = wizard_view.bot.get_channel(int(wizard_view.data["channel_id"]))
            if chan:
                target_chan = chan
            else:
                try:
                    target_chan = await wizard_view.bot.fetch_channel(int(wizard_view.data["channel_id"]))
                except Exception as e:
                    log.warning(
                        "[Wizard] fetch_channel %s: %s",
                        wizard_view.data.get("channel_id"),
                        e,
                    )
                    
        # Persist event to Database
        if wizard_view.is_edit:
            if wizard_view.bulk_ids:
                await database.update_active_events_metadata_bulk(wizard_view.bulk_ids, wizard_view.data)
            else:
                await database.update_active_event(event_id, wizard_view.data)
        else:
            existing = await database.get_active_event(event_id, wizard_view.guild_id)
            target_cid = target_chan.id if target_chan else interaction.channel_id
            if not existing:
                await database.create_active_event(
                    guild_id=wizard_view.guild_id,
                    event_id=event_id,
                    config_name=str(wizard_view.data.get("config_name") or "manual"),
                    channel_id=target_cid,
                    start_time=wizard_view.data["start_time"],
                    data=wizard_view.data
                )
            else:
                await database.update_active_event(event_id, wizard_view.data)

        if wizard_view.is_edit:
            target_ids = wizard_view.bulk_ids if wizard_view.bulk_ids else [event_id]
            
            for eid in target_ids:
                curr_db_event = await database.get_active_event(eid, wizard_view.guild_id)
                if curr_db_event and curr_db_event.get("message_id") and curr_db_event.get("channel_id"):
                    channel = wizard_view.bot.get_channel(curr_db_event["channel_id"])
                    if channel:
                        try:
                            msg = await channel.fetch_message(curr_db_event["message_id"])
                            view = DynamicEventView(wizard_view.bot, eid, wizard_view.data)
                            await view.prepare()
                            await msg.edit(view=view)
                        except Exception as e:
                            log.error(f"Error updating message {eid}: {e}")
            
            msg_text = t("MSG_BULK_UPDATE_DONE", guild_id=wizard_view.guild_id) if wizard_view.bulk_ids else t("MSG_UPDATED", guild_id=wizard_view.guild_id)
            await interaction.followup.send(msg_text, ephemeral=True)
        else:
            view = DynamicEventView(wizard_view.bot, event_id, wizard_view.data)
            await view.prepare()
            
            ping_role_id = wizard_view.data.get("ping_role")
            ping_prefix = ""
            if ping_role_id and str(ping_role_id).isdigit() and int(ping_role_id) > 0:
                ping_prefix = f"{PING} <@&{ping_role_id}> "
            
            promo_msg = t("MSG_DEFAULT_PROMO", guild_id=wizard_view.guild_id)
            promo_content = f"{ping_prefix}{promo_msg}".strip()
            
            if promo_content:
                await target_chan.send(content=promo_content)
            
            msg = await target_chan.send(view=view)
            await database.set_event_message(event_id, msg.id)
            wizard_view.bot.add_view(view)

            # Automatic Discussion Thread Creation
            if wizard_view.data.get("use_threads"):
                try:
                    title = wizard_view.data.get("title") or "Event"
                    thread_name = title
                    
                    start_ts = wizard_view.data.get("start_time")
                    if start_ts and not wizard_view.data.get("lobby_mode"):
                        dt = datetime.datetime.fromtimestamp(float(start_ts))
                        thread_name = f"{title} - {dt.strftime('%m/%d')}"
                    
                    thread = await msg.create_thread(name=thread_name[:100])
                    
                    # Store thread_id in extra_data
                    extra_dto = parse_extra_data(wizard_view.data.get("extra_data"))
                    extra_dto.thread_id = thread.id
                    wizard_view.data["extra_data"] = extra_dto.to_json()
                    await database.update_active_event(event_id, wizard_view.data)
                    
                    log.info(f"[Wizard] Created thread '{thread_name}' for event {event_id}")
                except Exception as te:
                    log.error(f"[Wizard] Failed to create thread: {te}")

            await interaction.followup.send(
                t("MSG_PUBLISHED_IN_CHANNEL", guild_id=wizard_view.guild_id, channel_id=target_chan.id),
                ephemeral=True,
            )

        if wizard_view.data.get("draft_id"):
            await database.delete_draft(wizard_view.data.get("draft_id"), wizard_view.guild_id)

        await interaction.delete_original_response()
        wizard_view.stop()
    except Exception as e:
        log.error(f"[Wizard] Publish failed: {e}", exc_info=True)
        await interaction.followup.send(
            t('ERR_PUBLISH_FAILED', guild_id=wizard_view.guild_id, e=str(e)),
            ephemeral=True,
        )
