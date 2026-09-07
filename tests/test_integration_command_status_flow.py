from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.event_commands.helpers import handle_status_change


@pytest.mark.asyncio
async def test_integration_status_change_cancel_single_event():
    """Integration: Admin cancels a single event -> updates DB status and responds with confirmation."""
    bot = MagicMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    db_event = {"event_id": "EVT-100", "config_name": "manual", "guild_id": 123456}

    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("cogs.event_commands.helpers.resolve_target_events", new_callable=AsyncMock, return_value=(db_event, [db_event], None)):
            with patch("database.update_event_status", new_callable=AsyncMock) as mock_update:
                await handle_status_change(
                    bot=bot,
                    interaction=interaction,
                    event_id="EVT-100",
                    status="cancelled",
                    notify_type="ping",
                )
                mock_update.assert_called_once_with("EVT-100", "cancelled")
                interaction.followup.send.assert_called_once()

@pytest.mark.asyncio
async def test_integration_status_change_postpone_with_new_time():
    """Integration: Admin postpones an event with a new time -> parses timestamp and updates DB."""
    bot = MagicMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    db_event = {"event_id": "EVT-200", "config_name": "manual", "guild_id": 123456}

    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("cogs.event_commands.helpers.resolve_target_events", new_callable=AsyncMock, return_value=(db_event, [db_event], None)):
            with patch("cogs.event_commands.helpers.update_event_time_parsed", new_callable=AsyncMock) as mock_time_update:
                with patch("database.update_event_status", new_callable=AsyncMock) as mock_status_update:
                    await handle_status_change(
                        bot=bot,
                        interaction=interaction,
                        event_id="EVT-200",
                        status="postponed",
                        notify_type="ping",
                        new_time="2026-11-20 20:00:00",
                    )
                    mock_time_update.assert_called_once_with("EVT-200", "2026-11-20 20:00:00")
                    mock_status_update.assert_called_once_with("EVT-200", "postponed")

@pytest.mark.asyncio
async def test_integration_status_change_admin_authorization_failure():
    """Integration: Non-admin interaction is rejected before event lookup."""
    bot = MagicMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.send_message = AsyncMock()

    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock, return_value=False):
        await handle_status_change(
            bot=bot,
            interaction=interaction,
            event_id="EVT-100",
            status="cancelled",
            notify_type="ping",
        )
        interaction.response.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_integration_status_change_series_choice_trigger():
    """Integration: Status change on series event triggers StatusChoiceView prompt."""
    bot = MagicMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    ev1 = {"event_id": "SERIES-1", "config_name": "raid_series", "guild_id": 123456}
    ev2 = {"event_id": "SERIES-2", "config_name": "raid_series", "guild_id": 123456}

    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("cogs.event_commands.helpers.resolve_target_events", new_callable=AsyncMock, return_value=(ev1, [ev1, ev2], None)):
            with patch("database.get_active_events_by_config", new_callable=AsyncMock, return_value=[ev1, ev2]):
                await handle_status_change(
                    bot=bot,
                    interaction=interaction,
                    event_id="SERIES-1",
                    status="cancelled",
                    notify_type="ping",
                    occurrence=None, # Prompt needed
                )
                interaction.followup.send.assert_called_once()
                call_kwargs = interaction.followup.send.call_args.kwargs
                assert "view" in call_kwargs

@pytest.mark.asyncio
async def test_integration_status_change_nonexistent_event():
    """Integration: Status change handles non-existent event ID gracefully with error response."""
    bot = MagicMock()
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild_id = 123456
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch("cogs.event_commands.helpers.is_admin", new_callable=AsyncMock, return_value=True):
        with patch("cogs.event_commands.helpers.resolve_target_events", new_callable=AsyncMock, return_value=(None, [], None)):
            await handle_status_change(
                bot=bot,
                interaction=interaction,
                event_id="INVALID_ID",
                status="cancelled",
                notify_type="ping",
            )
            interaction.followup.send.assert_called_once()
