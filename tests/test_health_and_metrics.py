from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import TestClient, TestServer
import discord
import pytest
from utils.health_server import HealthServer, start_health_server
from utils.metrics import MetricsRegistry


@pytest.fixture
def mock_bot():
    bot = MagicMock(spec=discord.Client)
    bot.latency = 0.0456
    bot.guilds = [MagicMock(id=1), MagicMock(id=2)]
    bot.users = [MagicMock(id=10), MagicMock(id=20), MagicMock(id=30)]
    bot.is_ready.return_value = True
    bot.is_closed.return_value = False
    return bot


def test_metrics_registry_recording():
    """Verifies counter and gauge recordings in MetricsRegistry."""
    reg = MetricsRegistry()
    assert reg.uptime_seconds >= 0.0

    # Record commands
    reg.record_command("event create", status="success")
    reg.record_command("event create", status="success")
    reg.record_command("event delete", status="error")

    # Record errors
    reg.record_error("CheckFailure")
    reg.record_error("NotFound")

    # Record reminders
    reg.record_reminder_sent("dm")
    reg.record_reminder_sent("ping")

    # Record RSVPs
    reg.record_rsvp("accepted")
    reg.record_rsvp("wait_accepted")

    assert reg._command_counts[("event create", "success")] == 2
    assert reg._command_counts[("event delete", "error")] == 1
    assert reg._error_counts["CheckFailure"] == 1
    assert reg._reminder_counts["dm"] == 1
    assert reg._rsvp_counts["accepted"] == 1


@pytest.mark.asyncio
async def test_prometheus_exposition_generation(mock_bot):
    """Verifies that generated Prometheus metrics strictly adhere to text exposition standard."""
    reg = MetricsRegistry()
    reg.record_command("create", status="success")
    reg.record_error("ValueError")
    reg.record_reminder_sent("dm")
    reg.record_rsvp("tentative")

    db_stats = {"events": 12, "rsvps": 48, "guilds": 5}
    payload = await reg.generate_prometheus_metrics(mock_bot, db_stats=db_stats)

    # Check Prometheus metric headers & types
    assert "# HELP nexus_info" in payload
    assert "# TYPE nexus_info gauge" in payload
    assert 'nexus_info{version="1.0.0"' in payload

    assert "# HELP nexus_uptime_seconds" in payload
    assert "# TYPE nexus_uptime_seconds gauge" in payload
    assert "nexus_uptime_seconds" in payload

    assert "# HELP nexus_gateway_latency_seconds" in payload
    assert "nexus_gateway_latency_seconds 0.0456" in payload

    assert "# HELP nexus_guilds_count" in payload
    assert "nexus_guilds_count 2" in payload

    assert "# HELP nexus_active_events_count" in payload
    assert "nexus_active_events_count 12" in payload

    assert "# HELP nexus_db_total_rsvps" in payload
    assert "nexus_db_total_rsvps 48" in payload

    assert 'nexus_commands_total{command="create",status="success"} 1' in payload
    assert 'nexus_errors_total{type="ValueError"} 1' in payload
    assert 'nexus_reminders_dispatched_total{method="dm"} 1' in payload
    assert 'nexus_rsvps_action_total{status="tentative"} 1' in payload


@pytest.mark.asyncio
async def test_health_server_endpoints(mock_bot):
    """Verifies all HTTP routes on the HealthServer application."""
    server = HealthServer(bot=mock_bot, host="127.0.0.1", port=8080)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # 1. Test Root /
        resp = await client.get("/")
        assert resp.status == 200
        data = await resp.json()
        assert data["service"] == "Nexus Discord Bot"
        assert data["endpoints"]["liveness"] == "/healthz"

        # 2. Test Liveness /healthz
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data

        # 3. Test Readiness /readyz when healthy
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_manager = MagicMock()
        mock_manager.is_initialized = True
        mock_manager.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("database.db_manager", mock_manager):
            resp = await client.get("/readyz")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ready"
            assert "connected" in data["checks"]["discord_gateway"]
            assert data["checks"]["database"] == "connected"

        # 4. Test Readiness /readyz when degraded (bot not ready)
        mock_bot.is_ready.return_value = False
        with patch("database.db_manager", mock_manager):
            resp = await client.get("/readyz")
            assert resp.status == 503
            data = await resp.json()
            assert data["status"] == "degraded"
            assert "not ready" in data["checks"]["discord_gateway"]

        # 5. Test Readiness /readyz when degraded (database offline)
        mock_bot.is_ready.return_value = True
        mock_manager.is_initialized = False
        with patch("database.db_manager", mock_manager):
            resp = await client.get("/readyz")
            assert resp.status == 503
            data = await resp.json()
            assert data["status"] == "degraded"
            assert "disconnected" in data["checks"]["database"]

        # 6. Test Prometheus Exporter /metrics
        resp = await client.get("/metrics")
        assert resp.status == 200
        assert resp.content_type == "text/plain"
        text = await resp.text()
        assert "nexus_uptime_seconds" in text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_health_server_start_stop_lifecycle(mock_bot):
    """Verifies starting and stopping the HealthServer instance."""
    with patch("aiohttp.web.TCPSite") as mock_site_cls, \
         patch("aiohttp.web.AppRunner") as mock_runner_cls:

        mock_runner = MagicMock()
        mock_runner.setup = AsyncMock()
        mock_runner.cleanup = AsyncMock()
        mock_runner_cls.return_value = mock_runner

        mock_site = MagicMock()
        mock_site.start = AsyncMock()
        mock_site_cls.return_value = mock_site

        server = await start_health_server(mock_bot, host="127.0.0.1", port=9999)
        assert server is not None
        assert server.port == 9999
        mock_runner.setup.assert_called_once()
        mock_site.start.assert_called_once()

        await server.stop()
        mock_runner.cleanup.assert_called_once()
