import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
import discord
from utils.config import Config
from utils.auth import is_admin, is_master

@pytest.mark.asyncio
async def test_is_admin_bot_owner():
    """Test bot owner always has admin permissions and bypasses restrictions."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.guild_id = 123456
    interaction.channel_id = 789012
    interaction.client = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=True)

    assert await is_admin(interaction) is True

@pytest.mark.asyncio
async def test_is_admin_guild_admin_permission():
    """Test user with Discord Administrator permission is authorized."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions.administrator = True
    interaction.guild_id = 123456
    interaction.channel_id = 789012
    interaction.client = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=False)

    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = {"admin_role_ids": "", "admin_channel_ids": ""}
        assert await is_admin(interaction) is True

@pytest.mark.asyncio
async def test_is_admin_allowed_role():
    """Test user with a configured admin role is authorized."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    
    role1 = MagicMock()
    role1.id = 555666
    interaction.user.roles = [role1]
    interaction.guild_id = 123456
    interaction.channel_id = 789012
    interaction.client = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=False)

    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = {"admin_role_ids": "555666, 777888", "admin_channel_ids": ""}
        assert await is_admin(interaction) is True

@pytest.mark.asyncio
async def test_is_admin_channel_restriction():
    """Test admin check fails if interaction is executed outside of configured admin channels."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.guild_permissions.administrator = True
    interaction.guild_id = 123456
    interaction.channel_id = 999999 # Wrong channel
    interaction.client = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=False)

    with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = {"admin_role_ids": "", "admin_channel_ids": "111222, 333444"}
        assert await is_admin(interaction) is False

@pytest.mark.asyncio
async def test_is_master_check():
    """Test is_master validates whether guild is in config.master_guild_ids."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.guild_id = 999111
    interaction.channel_id = 123
    interaction.client = MagicMock()
    interaction.client.is_owner = AsyncMock(return_value=False)
    interaction.user.guild_permissions.administrator = True

    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[999111]):
        with patch("database.get_all_guild_settings", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {"admin_role_ids": "", "admin_channel_ids": ""}
            assert await is_master(interaction) is True

    # Non-master guild
    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[888222]):
        assert await is_master(interaction) is False
