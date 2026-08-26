import io
import csv
import time
import datetime
from typing import Any, Optional
import discord
from utils.calendar_utils import generate_ics_batch

def generate_events_csv(events: list[dict[str, Any]]) -> str:
    """Converts guild event records into a formatted CSV string."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Event ID", "Title", "Creator ID", "Start Time", "Status", "Template", "Total RSVPs", "No-shows"])

    for e in events:
        st = datetime.datetime.fromtimestamp(e["start_time"]).strftime("%Y-%m-%d %H:%M") if e.get("start_time") else "Lobby"
        writer.writerow([
            e.get("event_id", ""),
            e.get("title", ""),
            e.get("creator_id", ""),
            st,
            e.get("status", ""),
            e.get("config_name", ""),
            e.get("total_rsvps", 0),
            e.get("no_shows", 0),
        ])

    return buffer.getvalue()

def generate_rsvps_csv(rsvps: list[dict[str, Any]]) -> str:
    """Converts guild RSVP details into a formatted CSV string."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Event Title", "User ID", "Status", "Joined At", "Attendance"])

    for r in rsvps:
        ja = datetime.datetime.fromtimestamp(r["joined_at"]).strftime("%Y-%m-%d %H:%M") if r.get("joined_at") else ""
        writer.writerow([
            r.get("event_title", ""),
            r.get("user_id", ""),
            r.get("status", ""),
            ja,
            r.get("attendance", ""),
        ])

    return buffer.getvalue()

def create_csv_discord_file(csv_text: str, filename: str) -> discord.File:
    """Packages a CSV string into a discord.File object ready for upload."""
    buffer = io.StringIO(csv_text)
    return discord.File(buffer, filename=filename)

def generate_future_events_ics_file(events: list[dict[str, Any]], guild_id: int | str, horizon_seconds: int = 86400) -> Optional[discord.File]:
    """Filters future events and generates a downloadable .ics calendar file."""
    now = time.time()
    future_events = [e for e in events if (e.get("start_time") or 0) > (now - horizon_seconds)]
    if not future_events:
        return None

    ics_text = generate_ics_batch(future_events)
    buffer = io.BytesIO(ics_text.encode("utf-8"))
    return discord.File(buffer, filename=f"events_{guild_id}.ics")
