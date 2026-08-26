import uuid
import json
from typing import Any, Optional
import discord
import database
from database import DEFAULT_TIMEZONE
from utils.emojis import (
    SUCCESS, ERROR, INFO,
    REC_DAILY, REC_WEEKLY, REC_MONTHLY, REC_BIWEEKLY,
    REC_WEEKDAYS, REC_WEEKENDS, REC_CUSTOM, REC_RELATIVE
)
from utils.i18n import t
from utils.templates import ICON_SET_TEMPLATES
from utils.emoji_utils import to_emoji, make_select_option
from utils.discord_utils import resolve_channel

class WizardState:
    """Manages event wizard form state, default settings, and draft persistence."""

    def __init__(
        self,
        bot: discord.Client,
        creator_id: int,
        guild_id: Optional[int] = None,
        existing_data: Optional[dict[str, Any]] = None,
        is_edit: bool = False,
        bulk_ids: Optional[list[str]] = None,
        wizard_type: Optional[str] = None,
    ):
        self.bot = bot
        self.creator_id = creator_id
        self.guild_id = guild_id
        self.is_edit = is_edit
        self.bulk_ids = bulk_ids
        self.data: dict[str, Any] = dict(existing_data or {})

        # Determine wizard_type
        if wizard_type:
            self.wizard_type = wizard_type
        elif self.data.get("wizard_type"):
            self.wizard_type = self.data["wizard_type"]
        elif self.data.get("lobby_mode"):
            self.wizard_type = "lobby"
        elif self.data.get("recurrence_type") and self.data["recurrence_type"] != "none":
            self.wizard_type = "series"
        else:
            self.wizard_type = "single"

        self.data["wizard_type"] = self.wizard_type
        self.can_publish: bool = False
        self.chan_warning: str = ""

        # Step completions
        if self.wizard_type == "lobby":
            s1 = bool(self.data.get("title"))
        elif self.wizard_type in ("single", "series"):
            s1 = bool(self.data.get("title") and self.data.get("start_str"))
        else:
            s1 = bool(self.data.get("title"))

        self.steps_completed: dict[str, bool] = {
            "step1": s1,
            "step2": (bool(self.data.get("recurrence_type")) and self.data.get("recurrence_type") != "none") if self.wizard_type == "series" else True,
            "step3": True,
        }

        self.icon_set_options: list[discord.SelectOption] = []
        self.recurrence_options: list[discord.SelectOption] = []

    async def load_defaults(self) -> None:
        """Loads server defaults, normalizes fields, and resolves channel."""
        current_set = self.data.get("icon_set", "standard")
        current_rec = self.data.get("recurrence_type", "none")

        # Load server defaults if missing
        if "repost_offset" not in self.data:
            self.data["repost_offset"] = await database.get_guild_setting(self.guild_id, "default_repost_offset", default="12h")
        if "repost_trigger" not in self.data:
            self.data["repost_trigger"] = await database.get_guild_setting(self.guild_id, "default_repost_trigger", default="after_end")
        if "reminder_offset" not in self.data:
            self.data["reminder_offset"] = await database.get_guild_setting(self.guild_id, "default_reminder_offset", default="")
        if "reminder_type" not in self.data:
            self.data["reminder_type"] = await database.get_guild_setting(self.guild_id, "reminder_type", default="none")
        if "reminder_offsets" not in self.data:
            ev_id = self.data.get("event_id")
            if ev_id:
                rem_rows = await database.get_event_reminders(ev_id)
                if rem_rows:
                    self.data["reminder_offsets"] = [r["offset_str"] for r in rem_rows]
                    self.data["reminder_messages"] = [r["custom_message"] for r in rem_rows]
                else:
                    def_ro = self.data.get("reminder_offset") or await database.get_guild_setting(
                        self.guild_id, "default_reminder_offset", default=""
                    )
                    ro_list = [x.strip() for x in def_ro.splitlines() if x.strip()]
                    rt = self.data.get("reminder_type") or await database.get_guild_setting(self.guild_id, "reminder_type", default="none")
                    self.data["reminder_offsets"] = ro_list if rt != "none" else []
                    self.data["reminder_messages"] = []
            else:
                def_ro = await database.get_guild_setting(self.guild_id, "default_reminder_offset", default="")
                ro_list = [x.strip() for x in def_ro.splitlines() if x.strip()]
                rt = self.data.get("reminder_type") or await database.get_guild_setting(
                    self.guild_id, "reminder_type", default="none"
                )
                self.data["reminder_type"] = rt
                self.data["reminder_offsets"] = ro_list if rt != "none" else []
                self.data["reminder_messages"] = []
        if not (self.data.get("reminder_message") or "").strip() and self.data.get("extra_data"):
            try:
                ed = (
                    json.loads(self.data["extra_data"])
                    if isinstance(self.data["extra_data"], str)
                    else self.data["extra_data"]
                )
                if isinstance(ed, dict):
                    self.data["reminder_message"] = (
                        (ed.get("custom_reminder_msg") or "").strip() or None
                    )
            except Exception:
                pass
        if "color" not in self.data:
            self.data["color"] = await database.get_guild_setting(self.guild_id, "default_color", default="0x40C4FF")
        self.data["rsvp_allowed_role_ids"] = database.normalize_rsvp_allowed_role_ids_value(
            self.data.get("rsvp_allowed_role_ids")
        )
        if "timezone" not in self.data:
            self.data["timezone"] = await database.get_guild_setting(self.guild_id, "timezone", default=DEFAULT_TIMEZONE)

        if self.wizard_type == "lobby":
            self.data["lobby_mode"] = True
            self.data["use_waiting_list"] = False
            self.data["reminder_offsets"] = []
            if "lobby_expire_offset" not in self.data:
                self.data["lobby_expire_offset"] = "12h"
            if self.is_edit:
                rt = (self.data.get("reminder_type") or "none").strip().lower()
                if rt in ("none", "") and self.data.get("lobby_remind_on_fill", True):
                    g_rt = (
                        await database.get_guild_setting(self.guild_id, "reminder_type", default="none")
                        or "none"
                    ).strip().lower()
                    if g_rt not in ("none", ""):
                        self.data["reminder_type"] = g_rt

        if "max_accepted" not in self.data:
            m = await database.get_guild_setting(self.guild_id, "default_max_participants", default="0")
            self.data["max_accepted"] = int(m) if str(m).isdigit() else 0

        # Resolve target channel
        self.chan_warning = ""
        raw_ch = self.data.get("channel_id")
        if not raw_ch:
            raw_ch = await database.get_guild_setting(self.guild_id, "default_event_channel", default="")

        if raw_ch:
            guild = self.bot.get_guild(int(self.guild_id)) if self.guild_id else None
            if guild:
                ch_id = await resolve_channel(guild, raw_ch)
                if ch_id:
                    self.data["channel_id"] = ch_id
                else:
                    self.chan_warning = t("MSG_CHANNEL_NOT_FOUND", guild_id=self.guild_id).format(name=raw_ch)

        if "use_waiting_list" not in self.data:
            val = await database.get_guild_setting(self.guild_id, "default_use_waiting_list", default="false")
            self.data["use_waiting_list"] = val.lower() == "true"

        if "use_temp_role" not in self.data:
            val = await database.get_guild_setting(self.guild_id, "default_use_temp_role", default="false")
            self.data["use_temp_role"] = val.lower() == "true"

        # Build options for hardcoded icon set templates
        self.icon_set_options = []
        for k, v in ICON_SET_TEMPLATES.items():
            label = t(v["label_key"], guild_id=self.guild_id)
            self.icon_set_options.append(make_select_option(
                label=label[:100],
                value=k,
                emoji=to_emoji(v["emoji"]) or None,
                default=(current_set == k)
            ))

        # Build options for database custom emoji sets
        db_sets = await database.get_emoji_sets(self.guild_id)
        for s in db_sets:
            if s["set_id"] in ICON_SET_TEMPLATES:
                continue
            label = s["name"][:100]
            self.icon_set_options.append(make_select_option(
                label=label,
                value=s["set_id"],
                default=(current_set == s["set_id"])
            ))

        rec_types = [
            ("daily", REC_DAILY), ("weekly", REC_WEEKLY), ("monthly", REC_MONTHLY),
            ("biweekly", REC_BIWEEKLY), ("weekdays", REC_WEEKDAYS), ("weekends", REC_WEEKENDS),
            ("custom", REC_CUSTOM), ("relative", REC_RELATIVE)
        ]
        self.recurrence_options = [
            make_select_option(label=t(f"SEL_REC_{k.upper()}", guild_id=self.guild_id), value=k, emoji=to_emoji(e), default=(current_rec == k))
            for k, e in rec_types
        ]

    def get_status_text(self) -> str:
        """Renders summary status lines for steps."""
        gid = self.guild_id
        s1 = SUCCESS if self.steps_completed["step1"] else ERROR
        opt_text = f"{INFO} {t('LBL_OPTIONAL', guild_id=gid)}"

        line1 = f"{t('STATUS_STEP1_EMOJI', guild_id=gid)} {t('STATUS_STEP1_LBL', guild_id=gid)}: {s1}"

        if self.wizard_type in ("single", "lobby"):
            s2 = SUCCESS if self.data.get("step2_opened") else opt_text
            line2 = f"{t('STATUS_STEP2_EMOJI', guild_id=gid)} {t('STATUS_STEP2_LBL', guild_id=gid)}: {s2}"
            return f"{line1}\n{line2}"
        else:
            # Series
            s2 = SUCCESS if self.steps_completed.get("step2") else ERROR
            s3 = SUCCESS if self.data.get("step3_opened") else opt_text
            line2 = f"{t('STATUS_STEP2_EMOJI', guild_id=gid)} {t('STATUS_STEP2_SERIES_LBL', guild_id=gid)}: {s2}"
            line3 = f"{t('STATUS_STEP3_EMOJI', guild_id=gid)} {t('STATUS_STEP3_LBL', guild_id=gid)}: {s3}"
            return f"{line1}\n{line2}\n{line3}"

    async def save_to_draft(self) -> None:
        """Persists the current form state to drafts table."""
        self.can_publish = False
        if not self.data.get("draft_id"):
            self.data["draft_id"] = str(uuid.uuid4())[:8]
        await database.save_draft(
            self.guild_id, self.data["draft_id"], str(self.creator_id),
            self.data.get("title") or "manual", self.data
        )
