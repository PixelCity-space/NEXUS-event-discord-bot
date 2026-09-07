from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.attendance.cogs.attendance_cog import AttendanceCog
from cogs.attendance.views.attendance_view import AttendanceView
from database.repositories.rsvps import (
    get_event_reliability_audit,
    get_guild_reliability_stats,
)


@pytest.mark.asyncio
async def test_integration_attendance_cog_manage_success_flow():
    """Integration: Admin executes /attendance manage -> verifies permissions -> creates AttendanceView -> sends followup."""
    bot = MagicMock()
    cog = AttendanceCog(bot)

    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    db_event = {"event_id": "EVT-ATT-1", "icon_set": "standard", "title": "Friday Boss Fight"}
    eligible = [
        {"user_id": 101, "status": "i_m_coming", "attendance": "present"},
        {"user_id": 102, "status": "i_m_coming", "attendance": "no_show"},
    ]

    with patch("cogs.attendance.cogs.attendance_cog.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("database.get_active_event", new_callable=AsyncMock, return_value=db_event):
            with patch("cogs.attendance.cogs.attendance_cog.get_eligible_attendance_participants", new_callable=AsyncMock, return_value=eligible):
                with patch.object(AttendanceView, "build", new_callable=AsyncMock) as mock_build:
                    await cog.manage_attendance.callback(cog, interaction, event_id="EVT-ATT-1")
                    interaction.response.defer.assert_called_once_with(ephemeral=True)
                    mock_build.assert_called_once()
                    interaction.followup.send.assert_called_once()
                    call_kwargs = interaction.followup.send.call_args.kwargs
                    assert "view" in call_kwargs
                    assert isinstance(call_kwargs["view"], AttendanceView)

@pytest.mark.asyncio
async def test_integration_attendance_cog_rejection_flows():
    """Integration: Tests error response paths in /attendance manage (non-admin, not found, no rsvps)."""
    bot = MagicMock()
    cog = AttendanceCog(bot)

    # 1. Non-admin rejection
    int_non_admin = MagicMock(spec=discord.Interaction)
    int_non_admin.guild_id = 123456
    int_non_admin.response.defer = AsyncMock()
    int_non_admin.followup.send = AsyncMock()

    with patch("cogs.attendance.cogs.attendance_cog.is_admin", new_callable=AsyncMock, return_value=False):
        await cog.manage_attendance.callback(cog, int_non_admin, event_id="EVT-1")
        int_non_admin.followup.send.assert_called_once()

    # 2. Event not found
    int_not_found = MagicMock(spec=discord.Interaction)
    int_not_found.guild_id = 123456
    int_not_found.response.defer = AsyncMock()
    int_not_found.followup.send = AsyncMock()

    with patch("cogs.attendance.cogs.attendance_cog.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("database.get_active_event", new_callable=AsyncMock, return_value=None):
            mock_pool = MagicMock()
            mock_pool.fetchrow = AsyncMock(return_value=None)
            with patch("database.get_pool", return_value=mock_pool):
                await cog.manage_attendance.callback(cog, int_not_found, event_id="INVALID")
                int_not_found.followup.send.assert_called_once()

    # 3. No eligible RSVPs
    int_no_rsvps = MagicMock(spec=discord.Interaction)
    int_no_rsvps.guild_id = 123456
    int_no_rsvps.response.defer = AsyncMock()
    int_no_rsvps.followup.send = AsyncMock()

    db_event = {"event_id": "EVT-EMPTY", "icon_set": "standard", "title": "Empty Event"}
    with patch("cogs.attendance.cogs.attendance_cog.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("database.get_active_event", new_callable=AsyncMock, return_value=db_event):
            with patch("cogs.attendance.cogs.attendance_cog.get_eligible_attendance_participants", new_callable=AsyncMock, return_value=[]):
                await cog.manage_attendance.callback(cog, int_no_rsvps, event_id="EVT-EMPTY")
                int_no_rsvps.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_integration_attendance_view_build_and_toggle_callback():
    """Integration: Full AttendanceView build lifecycle, member resolution, and button toggle callback."""
    bot = MagicMock()
    participants = [
        {"user_id": 101, "status": "i_m_coming", "attendance": "present"},
        {"user_id": 102, "status": "i_m_coming", "attendance": "no_show"},
    ]

    view = AttendanceView(bot, "EVT-100", participants, guild_id="123456", title="Raid Night")

    with patch("cogs.attendance.views.attendance_view.resolve_member_names_batch", new_callable=AsyncMock) as mock_names:
        mock_names.return_value = {"101": "TankMaster", "102": "HealBot"}
        await view.build()

        assert len(view.children) > 0 # Main container added
        assert view.name_cache["101"] == "TankMaster"

        # Simulate user clicking the toggle button for User 101
        click_interaction = MagicMock(spec=discord.Interaction)
        click_interaction.response.defer = AsyncMock()
        click_interaction.response.is_done.return_value = True
        click_interaction.edit_original_response = AsyncMock()

        with patch("cogs.attendance.views.attendance_view.toggle_user_attendance", new_callable=AsyncMock, return_value="no_show") as mock_toggle:
            with patch.object(AttendanceView, "build", new_callable=AsyncMock):
                # Trigger the callback attached to User 101's toggle
                # Find container and section button
                container = view.children[0]
                toggle_btn = None
                for item in container.children:
                    if isinstance(item, discord.ui.Section):
                        toggle_btn = item.accessory
                        break

                assert toggle_btn is not None
                await toggle_btn.callback(click_interaction)
                mock_toggle.assert_called_once_with("EVT-100", "101", "present")
                assert participants[0]["attendance"] == "no_show"
                click_interaction.edit_original_response.assert_called_once()

@pytest.mark.asyncio
async def test_integration_attendance_view_pagination():
    """Integration: Multi-page AttendanceView navigates pages with prev/next buttons."""
    bot = MagicMock()
    # 7 participants -> 2 pages (5 on page 1, 2 on page 2)
    participants = [{"user_id": i, "status": "coming", "attendance": "present"} for i in range(1, 8)]

    view = AttendanceView(bot, "EVT-PAGED", participants, guild_id="123456", title="Big Event")

    with patch("cogs.attendance.views.attendance_view.resolve_member_names_batch", new_callable=AsyncMock, return_value={}):
        await view.build()
        assert view.page == 0

        # Find navigation ActionRow
        container = view.children[0]
        action_row = None
        for item in container.children:
            if isinstance(item, discord.ui.ActionRow):
                action_row = item
                break

        assert action_row is not None
        prev_btn, next_btn = action_row.children[0], action_row.children[1]

        # Next page click
        nav_interaction = MagicMock(spec=discord.Interaction)
        nav_interaction.response.defer = AsyncMock()
        nav_interaction.response.is_done.return_value = True
        nav_interaction.edit_original_response = AsyncMock()

        with patch.object(AttendanceView, "build", new_callable=AsyncMock):
            await next_btn.callback(nav_interaction)
            assert view.page == 1

            await prev_btn.callback(nav_interaction)
            assert view.page == 0

@pytest.mark.asyncio
async def test_integration_guild_and_event_reliability_audit():
    """Integration: Querying participant past attendance stats for audit view and guild stats."""
    mock_pool = MagicMock()
    audit_rows = [
        {"user_id": 101, "total_past_rsvps": 10, "noshow_count": 2},
        {"user_id": 102, "total_past_rsvps": 8, "noshow_count": 0},
    ]
    mock_pool.fetch = AsyncMock(return_value=audit_rows)

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        # 1. Event reliability audit
        rows_event = await get_event_reliability_audit("EVT-100", "123456")
        assert len(rows_event) == 2
        assert rows_event[0]["user_id"] == 101

        # 2. Guild reliability stats
        rows_guild = await get_guild_reliability_stats("123456", all_time=False)
        assert len(rows_guild) == 2
