import pytest
from unittest.mock import MagicMock, AsyncMock
from utils.discord_utils import (
    resolve_channel,
    resolve_role,
    resolve_user,
)

@pytest.mark.asyncio
async def test_resolve_channel_mention_and_id():
    """Test resolving a channel via <#ID> mention and direct numeric ID."""
    guild = MagicMock()
    mock_channel = MagicMock()
    mock_channel.id = 1122334455
    guild.get_channel.side_effect = lambda cid: mock_channel if cid == 1122334455 else None

    # Resolve from mention
    res_mention = await resolve_channel(guild, "<#1122334455>")
    assert res_mention == 1122334455

    # Resolve from raw integer
    res_int = await resolve_channel(guild, 1122334455)
    assert res_int == 1122334455

@pytest.mark.asyncio
async def test_resolve_channel_by_name():
    """Test resolving a channel by text name."""
    guild = MagicMock()
    guild.get_channel.return_value = None

    c1 = MagicMock()
    c1.name = "general"
    c1.id = 100
    c2 = MagicMock()
    c2.name = "events"
    c2.id = 200
    guild.channels = [c1, c2]

    res = await resolve_channel(guild, "events")
    assert res == 200

    res_hash = await resolve_channel(guild, "#general")
    assert res_hash == 100

@pytest.mark.asyncio
async def test_resolve_channel_none_or_missing():
    """Test resolve_channel with None or missing channel."""
    assert await resolve_channel(None, "general") is None
    assert await resolve_channel(MagicMock(), None) is None

    guild = MagicMock()
    guild.get_channel.return_value = None
    guild.channels = []
    assert await resolve_channel(guild, "non_existent_chan") is None

def test_resolve_role_mention_and_name():
    """Test resolving a Discord role via <@&ID>, @RoleName, or name."""
    guild = MagicMock()
    r1 = MagicMock()
    r1.name = "RaidLeader"
    r1.id = 998877
    guild.get_role.side_effect = lambda rid: r1 if rid == 998877 else None
    guild.roles = [r1]

    # Resolve from mention
    res_mention = resolve_role(guild, "<@&998877>")
    assert res_mention == r1

    # Resolve from role name with @
    res_name = resolve_role(guild, "@RaidLeader")
    assert res_name == r1

    # Missing role
    assert resolve_role(guild, "UnknownRole") is None
    assert resolve_role(None, "RaidLeader") is None

@pytest.mark.asyncio
async def test_resolve_user_invalid_or_none():
    """Test resolve_user handles None, empty string, or invalid user ID gracefully."""
    bot = MagicMock()
    assert await resolve_user(bot, None) is None
    assert await resolve_user(bot, "") is None
