import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from cogs.event_commands.views.history import EventHistoryView
from cogs.event_commands.views.my_events import MyEventsView
from cogs.event_ui.views.edit_choice import EditChoiceView
from cogs.event_ui.views.status_choice import StatusChoiceView

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    chan = MagicMock()
    msg = MagicMock()
    msg.edit = AsyncMock()
    chan.fetch_message = AsyncMock(return_value=msg)
    bot.get_channel.return_value = chan
    return bot

@pytest.fixture
def mock_interaction():
    inter = MagicMock(spec=discord.Interaction)
    inter.guild_id = 12345
    inter.channel_id = 67890
    inter.response = MagicMock()
    inter.response.defer = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter

@pytest.mark.asyncio
async def test_event_history_view_building_and_pagination(mock_bot, mock_interaction):
    events = [
        {
            "title": "Raid 1",
            "start_time": time.time() - 3600,
            "channel_id": "100",
            "message_id": "200",
            "creator_id": "999",
            "user_status": "accepted",
            "attendance": "present",
        },
        {
            "title": "Dungeon 2",
            "start_time": time.time() - 7200,
            "channel_id": "100",
            "message_id": "201",
            "creator_id": "888",
            "user_status": "tank",
            "attendance": "no_show",
        },
        {
            "title": "PvP Arena 3",
            "start_time": time.time() - 10800,
            "channel_id": "100",
            "message_id": "202",
            "creator_id": "888",
            "user_status": "dps",
            "attendance": "unmarked",
        },
        {
            "title": "Raid 4 (Page 2)",
            "start_time": None,
            "channel_id": "100",
            "message_id": "203",
            "creator_id": "999",
            "user_status": "accepted",
            "attendance": "present",
        },
    ]

    view = EventHistoryView(mock_bot, guild_id=12345, user_id=999, events=events)
    await view.build()
    assert len(view.children) > 0

    # Test pagination: find the container ActionRow containing prev/next buttons
    container = view.children[0]
    action_rows = [item for item in container.children if isinstance(item, discord.ui.ActionRow)]
    pagination_row = action_rows[-1]
    prev_btn, next_btn = pagination_row.children[0], pagination_row.children[1]

    # Trigger next page
    await next_btn.callback(mock_interaction)
    assert view.page == 1
    mock_interaction.response.edit_message.assert_called_once()

    # Trigger previous page
    mock_interaction.response.edit_message.reset_mock()
    await prev_btn.callback(mock_interaction)
    assert view.page == 0
    mock_interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
async def test_my_events_view_building_and_pagination(mock_bot, mock_interaction):
    events = [
        {
            "title": "Active Raid 1",
            "start_time": time.time() + 3600,
            "event_id": "EVT-1",
            "channel_id": "100",
            "message_id": "200",
            "creator_id": "999",
            "user_status": "accepted",
        },
        {
            "title": "Lobby Event 2",
            "start_time": None,
            "event_id": "EVT-2",
            "channel_id": "100",
            "message_id": "201",
            "creator_id": "777",
            "user_status": "tank",
        },
        {
            "title": "Dungeon 3",
            "start_time": time.time() + 7200,
            "event_id": "EVT-3",
            "channel_id": "100",
            "message_id": "202",
            "creator_id": "777",
            "user_status": "dps",
        },
        {
            "title": "Event 4 (Page 2)",
            "start_time": time.time() + 10800,
            "event_id": "EVT-4",
            "channel_id": "100",
            "message_id": "203",
            "creator_id": "999",
            "user_status": "accepted",
        },
    ]

    view = MyEventsView(mock_bot, guild_id=12345, user_id=999, events=events)
    await view.build()
    assert len(view.children) > 0

    container = view.children[0]
    action_rows = [item for item in container.children if isinstance(item, discord.ui.ActionRow)]
    pagination_row = action_rows[-1]
    prev_btn, next_btn = pagination_row.children[0], pagination_row.children[1]

    # Next page
    await next_btn.callback(mock_interaction)
    assert view.page == 1
    mock_interaction.response.edit_message.assert_called_once()

    # Prev page
    mock_interaction.response.edit_message.reset_mock()
    await prev_btn.callback(mock_interaction)
    assert view.page == 0
    mock_interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
async def test_edit_choice_view_callbacks(mock_bot, mock_interaction):
    db_event = {"event_id": "EVT-1", "guild_id": 12345}
    series_events = [{"event_id": "EVT-1"}, {"event_id": "EVT-2"}]

    view = EditChoiceView(mock_bot, "EVT-1", db_event, series_events)

    with patch("cogs.event_ui.views.dynamic_card.DynamicEventView._open_wizard", new_callable=AsyncMock) as mock_open:
        # 1. Single callback
        await view.edit_single_callback(mock_interaction)
        mock_open.assert_called_once_with(mock_interaction, db_event)

        # 2. Series callback
        mock_open.reset_mock()
        await view.edit_series_callback(mock_interaction)
        mock_open.assert_called_once_with(mock_interaction, db_event, bulk_ids=["EVT-1", "EVT-2"])

@pytest.mark.asyncio
async def test_status_choice_view_single_and_series(mock_bot, mock_interaction):
    db_event = {
        "event_id": "EVT-1",
        "title": "Weekly Raid",
        "guild_id": "12345",
        "channel_id": 67890,
        "message_id": 888888,
    }
    series_events = [{"event_id": "EVT-1"}, {"event_id": "EVT-2"}]

    view = StatusChoiceView(
        bot=mock_bot,
        event_id="EVT-1",
        db_event=db_event,
        series_events=series_events,
        new_status="cancelled",
        notify_type="channel",
    )

    with patch("database.update_event_status", new_callable=AsyncMock) as mock_up_single, \
         patch("database.update_event_status_bulk", new_callable=AsyncMock) as mock_up_bulk, \
         patch("database.get_active_event", new_callable=AsyncMock) as mock_get_ev, \
         patch("database.get_rsvps", new_callable=AsyncMock) as mock_get_rsvps, \
         patch("cogs.event_ui.views.dynamic_card.DynamicEventView.prepare", new_callable=AsyncMock) as mock_prep, \
         patch("cogs.event_ui.views.status_choice.send_event_alert", new_callable=AsyncMock) as mock_alert:

        mock_get_ev.return_value = db_event
        mock_get_rsvps.return_value = [{"user_id": 101, "status": "accepted"}]

        # 1. Single status change
        await view.status_single_callback(mock_interaction)
        mock_up_single.assert_called_once_with("EVT-1", "cancelled")
        mock_alert.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # 2. Series status change
        mock_alert.reset_mock()
        mock_interaction.followup.send.reset_mock()
        await view.status_series_callback(mock_interaction)
        mock_up_bulk.assert_called_once_with(["EVT-1", "EVT-2"], "cancelled")
        mock_alert.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
