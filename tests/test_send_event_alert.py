import pytest
from unittest.mock import MagicMock, AsyncMock
from services.notification_service import send_event_alert

@pytest.mark.asyncio
async def test_send_event_alert_method_none():
    """Test send_event_alert exits without sending when method is 'none'."""
    bot = MagicMock()
    stats = await send_event_alert(bot, 12345, [101, 102], method="none")
    assert stats == {"channel_sent": 0, "dms_sent": 0, "dms_failed": 0}
    bot.get_channel.assert_not_called()

@pytest.mark.asyncio
async def test_send_event_alert_channel_dispatch():
    """Test send_event_alert sends formatted message with user pings to the channel."""
    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    stats = await send_event_alert(
        bot=bot,
        channel_id=987654,
        target_user_ids=[101, 102],
        method="ping",
        content="Event is starting!",
    )
    assert stats["channel_sent"] == 1
    mock_channel.send.assert_called_once()
    call_kwargs = mock_channel.send.call_args.kwargs
    assert "<@101>, <@102>" in call_kwargs["content"]
    assert "Event is starting!" in call_kwargs["content"]

@pytest.mark.asyncio
async def test_send_event_alert_temp_role():
    """Test send_event_alert mentions temp role instead of individual user IDs when provided."""
    bot = MagicMock()
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    bot.get_channel.return_value = mock_channel

    stats = await send_event_alert(
        bot=bot,
        channel_id=987654,
        target_user_ids=[101, 102, 103],
        temp_role_id=555444,
        method="channel",
        content="Raid starting soon",
    )
    assert stats["channel_sent"] == 1
    call_kwargs = mock_channel.send.call_args.kwargs
    assert "<@&555444>" in call_kwargs["content"]
