from unittest.mock import PropertyMock, patch

import pytest

from utils.config import Config
from utils.tiers import (
    SubscriptionTier,
    get_guild_tier,
    is_master_guild,
    is_premium,
)


@pytest.mark.asyncio
async def test_get_guild_tier_master():
    """Test guild listed in master_guild_ids returns MASTER tier."""
    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[123456789]):
        with patch.object(Config, "premium_guild_ids", new_callable=PropertyMock, return_value=[987654321]):
            tier = await get_guild_tier(123456789)
            assert tier == SubscriptionTier.MASTER

@pytest.mark.asyncio
async def test_get_guild_tier_premium():
    """Test guild listed in premium_guild_ids returns PREMIUM tier."""
    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[123456789]):
        with patch.object(Config, "premium_guild_ids", new_callable=PropertyMock, return_value=[987654321]):
            tier = await get_guild_tier(987654321)
            assert tier == SubscriptionTier.PREMIUM

@pytest.mark.asyncio
async def test_get_guild_tier_standard():
    """Test unlisted guild returns STANDARD tier."""
    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[123456789]):
        with patch.object(Config, "premium_guild_ids", new_callable=PropertyMock, return_value=[987654321]):
            tier = await get_guild_tier(111222333)
            assert tier == SubscriptionTier.STANDARD

@pytest.mark.asyncio
async def test_is_premium_and_is_master_guild():
    """Test is_premium and is_master_guild helper booleans."""
    with patch.object(Config, "master_guild_ids", new_callable=PropertyMock, return_value=[100]):
        with patch.object(Config, "premium_guild_ids", new_callable=PropertyMock, return_value=[200]):
            # Master guild is also premium (tier >= PREMIUM)
            assert await is_premium(100) is True
            assert await is_master_guild(100) is True

            # Premium guild
            assert await is_premium(200) is True
            assert await is_master_guild(200) is False

            # Standard guild
            assert await is_premium(300) is False
            assert await is_master_guild(300) is False
