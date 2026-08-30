import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from database.repositories.rsvps import (
    promote_waiting_users_atomic,
    promote_next_waiting,
)

def _create_mock_pool(rsvps_in_db):
    mock_conn = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock()
    mock_conn.transaction.return_value.__aexit__ = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rsvps_in_db)
    mock_conn.execute = AsyncMock()

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    return mock_pool, mock_conn

@pytest.mark.asyncio
async def test_integration_waiting_list_promotion_fifo():
    """Integration: Atomic promotion promotes earliest queued waiting user (FIFO order)."""
    # 1 confirmed tank, 2 waiting tanks
    rsvps_in_db = [
        {"user_id": 101, "status": "tank", "joined_at": 1000},
        {"user_id": 102, "status": "wait_tank", "joined_at": 1010},
        {"user_id": 103, "status": "wait_tank", "joined_at": 1020},
    ]
    mock_pool, mock_conn = _create_mock_pool(rsvps_in_db)

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        promoted = await promote_waiting_users_atomic(
            event_id="EVT-100",
            positive_statuses=["tank"],
            max_accepted=2,
        )
        # Earliest waiting user (102) should be promoted
        assert promoted == [(102, "tank")]
        # Check DB update query was executed for user 102
        update_calls = [c for c in mock_conn.execute.call_args_list if "UPDATE rsvps" in str(c)]
        assert len(update_calls) == 1

@pytest.mark.asyncio
async def test_integration_waiting_list_role_limit_capped_promotion():
    """Integration: Atomic promotion skips waitlisted users whose target role is full and promotes eligible role."""
    # DPS is full (limit: 1, current: 1), Tank has open slot (limit: 1, current: 0)
    # Queue: 1st in line is DPS (capped), 2nd is Tank (eligible)
    rsvps_in_db = [
        {"user_id": 101, "status": "dps", "joined_at": 1000},
        {"user_id": 102, "status": "wait_dps", "joined_at": 1010},
        {"user_id": 103, "status": "wait_tank", "joined_at": 1020},
    ]
    mock_pool, mock_conn = _create_mock_pool(rsvps_in_db)

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        promoted = await promote_waiting_users_atomic(
            event_id="EVT-100",
            positive_statuses=["dps", "tank"],
            max_accepted=3,
            role_limits={"dps": 1, "tank": 1},
        )
        # Should skip user 102 (DPS full) and promote user 103 (Tank available)
        assert promoted == [(103, "tank")]

@pytest.mark.asyncio
async def test_integration_waiting_list_global_max_accepted_cutoff():
    """Integration: Atomic promotion stops when global max_accepted limit is reached."""
    # 1 open slot remaining (max_accepted=2, current active=1)
    rsvps_in_db = [
        {"user_id": 101, "status": "accepted", "joined_at": 1000},
        {"user_id": 102, "status": "wait_accepted", "joined_at": 1010},
        {"user_id": 103, "status": "wait_accepted", "joined_at": 1020},
    ]
    mock_pool, mock_conn = _create_mock_pool(rsvps_in_db)

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        promoted = await promote_waiting_users_atomic(
            event_id="EVT-100",
            positive_statuses=["accepted"],
            max_accepted=2,
        )
        # Exactly 1 user promoted before max_accepted limit is hit
        assert len(promoted) == 1
        assert promoted == [(102, "accepted")]

@pytest.mark.asyncio
async def test_integration_waiting_list_empty_queue_handling():
    """Integration: Atomic promotion cleanly returns empty list when no users are waiting."""
    rsvps_in_db = [
        {"user_id": 101, "status": "tank", "joined_at": 1000},
        {"user_id": 102, "status": "heal", "joined_at": 1010},
    ]
    mock_pool, mock_conn = _create_mock_pool(rsvps_in_db)

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        promoted = await promote_waiting_users_atomic(
            event_id="EVT-100",
            positive_statuses=["tank", "heal"],
            max_accepted=5,
        )
        assert promoted == []

@pytest.mark.asyncio
async def test_integration_single_user_promote_next_waiting():
    """Integration: promote_next_waiting helper finds earliest waiting record and updates status."""
    mock_pool = MagicMock()
    mock_pool.fetchrow = AsyncMock(return_value={"user_id": "999"})
    mock_pool.execute = AsyncMock()

    with patch("database.repositories.rsvps.get_pool", return_value=mock_pool):
        promoted_uid = await promote_next_waiting("EVT-1", "wait_dps", "dps")
        assert promoted_uid == 999
        mock_pool.execute.assert_called_once()
