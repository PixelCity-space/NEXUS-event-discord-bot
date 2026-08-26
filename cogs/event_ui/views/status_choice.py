import discord
import database
from utils.emojis import PING
from utils.emoji_utils import make_button
from utils.i18n import t
from utils.logger import log
from services.notification_service import resolve_target_recipients, send_event_alert

class StatusChoiceView(discord.ui.View):
    """Prompt view to choose between changing status of a single instance or the entire series."""

    def __init__(self, bot: discord.Client, event_id: str, db_event: dict, series_events: list, new_status: str, notify_type: str = "none"):
        super().__init__(timeout=180)
        self.bot = bot
        self.event_id = event_id
        self.db_event = db_event
        self.series_events = series_events
        self.new_status = new_status
        self.notify_type = notify_type
        guild_id = db_event.get("guild_id")

        btn_single = make_button(label=t("BTN_SINGLE_INSTANCE", guild_id=guild_id), style=discord.ButtonStyle.secondary)
        btn_single.callback = self.status_single_callback
        self.add_item(btn_single)

        btn_series = make_button(label=t("BTN_ENTIRE_SERIES", guild_id=guild_id), style=discord.ButtonStyle.primary)
        btn_series.callback = self.status_series_callback
        self.add_item(btn_series)

    async def status_single_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await database.update_event_status(self.event_id, self.new_status)
        await self.refresh_and_notify(interaction, [self.event_id])
        await interaction.followup.send(t("MSG_STATUS_UPDATED", guild_id=interaction.guild_id, status=self.new_status), ephemeral=True)

    async def status_series_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ids = [ev['event_id'] for ev in self.series_events]
        await database.update_event_status_bulk(ids, self.new_status)
        await self.refresh_and_notify(interaction, ids)
        await interaction.followup.send(t("MSG_SERIES_UPDATED", guild_id=interaction.guild_id, status=self.new_status), ephemeral=True)

    async def refresh_and_notify(self, interaction: discord.Interaction, event_ids: list):
        from .dynamic_card import DynamicEventView
        for eid in event_ids:
            ev = await database.get_active_event(eid)
            if ev and ev.get("message_id") and ev.get("channel_id"):
                chan = self.bot.get_channel(ev["channel_id"])
                if chan:
                    try:
                        msg = await chan.fetch_message(ev["message_id"])
                        view = DynamicEventView(self.bot, eid, ev)
                        await view.prepare()
                        await msg.edit(view=view)
                    except Exception as e:
                        log.debug("refresh_and_notify edit %s: %s", eid, e)

        if self.notify_type == "none":
            return

        all_target_users = []
        for eid in event_ids:
            rsvps = await database.get_rsvps(eid)
            target_users = resolve_target_recipients(
                bot=self.bot,
                db_event=self.db_event,
                target_raw="all",
                rsvps=rsvps,
                active_set={},
            )
            all_target_users.extend(target_users)

        # Deduplicate
        participants = list(dict.fromkeys(all_target_users))
        if not participants:
            return

        guild_id = interaction.guild_id
        title = self.db_event.get('title') or 'Event'

        if self.new_status == "cancelled":
            msg_body = t("MSG_EVENT_CANCELLED", guild_id=guild_id, title=title)
        elif self.new_status == "postponed":
            msg_body = t("MSG_EVENT_POSTPONED", guild_id=guild_id, title=title)
        else:
            status_text = self.new_status.upper()
            msg_body = t("MSG_EVENT_NOTIF_PREFIX", guild_id=guild_id, status=status_text, title=title)

        notification_msg = f"{PING} {msg_body}"

        await send_event_alert(
            bot=self.bot,
            channel_id=interaction.channel_id,
            target_user_ids=participants,
            method=self.notify_type,
            content=notification_msg,
            dm_content=notification_msg,
            include_target_mentions=True,
        )
