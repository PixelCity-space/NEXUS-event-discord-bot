import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from services.attendance_service import (
    calculate_attendance_stats,
    get_eligible_attendance_participants,
    resolve_member_names_batch,
    toggle_user_attendance,
)
from services.export_service import (
    create_csv_discord_file,
    generate_events_csv,
    generate_future_events_ics_file,
    generate_rsvps_csv,
)


@pytest.mark.asyncio
async def test_integration_end_to_end_attendance_audit_flow():
    """Integration: Event completion -> participant retrieval -> attendance toggling -> stats calculation."""
    db_rsvps = [
        {"user_id": 101, "status": "tank", "attendance": "present"},
        {"user_id": 102, "status": "heal", "attendance": "present"},
        {"user_id": 103, "status": "dps", "attendance": "present"},
        {"user_id": 104, "status": "dps", "attendance": "present"},
        {"user_id": 105, "status": "not_coming", "attendance": None},
    ]

    with patch("database.get_event_attendance_data", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = db_rsvps
        # 1. Fetch eligible (positive) participants for 'mmo' template
        eligible = await get_eligible_attendance_participants("EVT-MMO-1", "mmo")
        assert len(eligible) == 4 # Users 101-104

        # 2. Initial stats: 4 attended, 0 no-show, 100%
        att, noshow, rate = calculate_attendance_stats(eligible)
        assert att == 4
        assert noshow == 0
        assert rate == 100.0

        # 3. Mark User 103 as no-show
        with patch("database.update_rsvp_attendance", new_callable=AsyncMock) as mock_update:
            new_att = await toggle_user_attendance("EVT-MMO-1", 103, "present")
            assert new_att == "no_show"
            mock_update.assert_called_once_with("EVT-MMO-1", 103, "no_show")

            # Update in local state
            for p in eligible:
                if p["user_id"] == 103:
                    p["attendance"] = "no_show"

            # 4. Recalculate stats: 3 attended, 1 no-show, 75%
            att2, noshow2, rate2 = calculate_attendance_stats(eligible)
            assert att2 == 3
            assert noshow2 == 1
            assert rate2 == 75.0

def test_integration_attendance_to_csv_export_discord_file():
    """Integration: Generating CSV exports -> packaging into Discord Attachment file."""
    events_data = [
        {
            "event_id": "EVT-2026",
            "title": "Season 4 Finals",
            "creator_id": "999888",
            "start_time": 1780000000,
            "status": "ended",
            "config_name": "tournament",
            "total_rsvps": 16,
            "no_shows": 2,
        }
    ]
    rsvps_data = [
        {
            "event_title": "Season 4 Finals",
            "user_id": "111222",
            "status": "accepted",
            "joined_at": 1779900000,
            "attendance": "present",
        }
    ]

    # Generate CSV strings
    events_csv = generate_events_csv(events_data)
    rsvps_csv = generate_rsvps_csv(rsvps_data)

    # Package into discord.File objects
    file_events = create_csv_discord_file(events_csv, "events_summary.csv")
    file_rsvps = create_csv_discord_file(rsvps_csv, "rsvps_summary.csv")

    assert isinstance(file_events, discord.File)
    assert file_events.filename == "events_summary.csv"
    assert isinstance(file_rsvps, discord.File)
    assert file_rsvps.filename == "rsvps_summary.csv"

def test_integration_future_events_ics_export_flow():
    """Integration: Filtering past events and creating an ICS Discord file attachment."""
    now = time.time()
    events = [
        # Past event (should be filtered out)
        {"event_id": "EV-PAST", "title": "Old Event", "start_time": now - 200000, "recurrence_type": "once"},
        # Future event
        {"event_id": "EV-FUTURE", "title": "Upcoming Tournament", "start_time": now + 86400, "end_time": now + 90000, "recurrence_type": "once"},
    ]

    ics_file = generate_future_events_ics_file(events, guild_id="123456")
    assert ics_file is not None
    assert isinstance(ics_file, discord.File)
    assert ics_file.filename == "events_123456.ics"

@pytest.mark.asyncio
async def test_integration_attendance_autocomplete_to_member_resolution():
    """Integration: Batch member name resolution with Discord API mock and cache."""
    bot = MagicMock()
    guild = MagicMock()
    m1 = MagicMock()
    m1.display_name = "DragonSlayer"
    guild.get_member.side_effect = lambda uid: m1 if uid == 101 else None
    bot.get_guild.return_value = guild

    name_cache = {"99": "AlreadyCachedUser"}
    resolved = await resolve_member_names_batch(
        bot=bot,
        guild_id="555",
        user_ids=["99", "101"],
        name_cache=name_cache,
    )
    assert resolved["99"] == "AlreadyCachedUser"
    assert resolved["101"] == "DragonSlayer"


@pytest.mark.asyncio
async def test_integration_batch_member_resolution_throttled():
    """Integration: Batch member name resolution fetches uncached members with semaphore throttling."""
    bot = MagicMock()
    guild = MagicMock()
    guild.get_member.return_value = None  # None cached locally

    async def mock_fetch_member(uid):
        m = MagicMock()
        m.display_name = f"Member_{uid}"
        return m

    guild.fetch_member = AsyncMock(side_effect=mock_fetch_member)
    bot.get_guild.return_value = guild

    user_ids = [str(i) for i in range(200, 210)]
    name_cache = {}
    resolved = await resolve_member_names_batch(
        bot=bot,
        guild_id="777",
        user_ids=user_ids,
        name_cache=name_cache,
    )

    assert len(resolved) == 10
    assert resolved["200"] == "Member_200"
    assert resolved["209"] == "Member_209"
    assert guild.fetch_member.call_count == 10


def test_integration_reliability_and_export_statistics():
    """Integration: Calculating reliability rates across multiple user records."""
    user_attendance_history = [
        {"attendance": "present"},
        {"attendance": "present"},
        {"attendance": "present"},
        {"attendance": "no_show"},
    ]
    attended, noshow, rate = calculate_attendance_stats(user_attendance_history)
    assert attended == 3
    assert noshow == 1
    assert rate == 75.0
