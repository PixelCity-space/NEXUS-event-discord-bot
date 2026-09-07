import asyncio
import os
import time
from typing import Optional
from aiohttp import web
import discord
from utils.logger import log
from utils.metrics import metrics


class HealthServer:
    """
    Lightweight asynchronous HTTP server providing liveness (/healthz),
    readiness (/readyz), and Prometheus metrics (/metrics) endpoints.
    Runs inside the bot's asyncio event loop.
    """

    def __init__(
        self,
        bot: discord.Client,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self.bot: discord.Client = bot
        self.host: str = host
        self.port: int = port
        self.app: web.Application = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Registers endpoint handlers."""
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/healthz", self.handle_healthz)
        self.app.router.add_get("/readyz", self.handle_readyz)
        self.app.router.add_get("/metrics", self.handle_metrics)

    async def handle_index(self, request: web.Request) -> web.Response:
        """Root status index."""
        return web.json_response({
            "service": "Nexus Discord Bot",
            "version": "1.0.0",
            "uptime_seconds": round(metrics.uptime_seconds, 2),
            "endpoints": {
                "liveness": "/healthz",
                "readiness": "/readyz",
                "metrics": "/metrics",
            },
        })

    async def handle_healthz(self, request: web.Request) -> web.Response:
        """
        Liveness probe: verifies that the HTTP server and event loop are responsive.
        Always returns 200 OK if the process loop is processing requests.
        """
        return web.json_response({
            "status": "ok",
            "uptime_seconds": round(metrics.uptime_seconds, 2),
            "timestamp": time.time(),
        }, status=200)

    async def handle_readyz(self, request: web.Request) -> web.Response:
        """
        Readiness probe: verifies dependencies (Discord Gateway connection & Database connection pool).
        Returns HTTP 200 when all dependencies are ready, HTTP 503 when degraded.
        """
        checks: dict[str, str] = {}
        all_ready = True

        # 1. Check Discord Gateway connection
        is_bot_ready = False
        try:
            is_bot_ready = self.bot.is_ready() and not self.bot.is_closed()
        except Exception:
            is_bot_ready = False

        if is_bot_ready:
            latency_ms = round((self.bot.latency or 0.0) * 1000, 2)
            checks["discord_gateway"] = f"connected ({latency_ms}ms)"
        else:
            checks["discord_gateway"] = "not ready or connecting"
            all_ready = False

        # 2. Check Database connection pool
        db_ready = False
        try:
            import database
            if hasattr(database, "db_manager") and database.db_manager.is_initialized:
                async with database.db_manager.acquire() as conn:
                    val = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=2.0)
                    if val == 1:
                        db_ready = True
        except Exception as e:
            checks["database_error"] = str(e)

        if db_ready:
            checks["database"] = "connected"
        else:
            checks["database"] = "disconnected or uninitialized"
            all_ready = False

        status_code = 200 if all_ready else 503
        return web.json_response({
            "status": "ready" if all_ready else "degraded",
            "checks": checks,
            "uptime_seconds": round(metrics.uptime_seconds, 2),
            "timestamp": time.time(),
        }, status=status_code)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """
        Prometheus metrics exposition endpoint.
        Returns metrics formatted in Prometheus text standard (text/plain; version=0.0.4).
        """
        db_stats = None
        try:
            import database
            if hasattr(database, "db_manager") and database.db_manager.is_initialized:
                db_stats = await database.get_global_stats()
        except Exception:
            pass

        content = await metrics.generate_prometheus_metrics(self.bot, db_stats=db_stats)
        return web.Response(
            text=content,
            content_type="text/plain",
            charset="utf-8",
            headers={"X-Prometheus-Refresh": "realtime"},
        )

    async def start(self) -> None:
        """Starts the aiohttp web server on the specified host and port."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            log.info("[HealthServer] HTTP liveness & metrics server listening on http://%s:%s", self.host, self.port)
        except Exception as e:
            log.error("[HealthServer] Failed to start HTTP health server on port %s: %s", self.port, e, exc_info=True)

    async def stop(self) -> None:
        """Gracefully shuts down the HTTP server and cleans up resources."""
        if self.runner:
            log.info("[HealthServer] Shutting down HTTP health server...")
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            log.info("[HealthServer] HTTP health server closed.")


async def start_health_server(
    bot: discord.Client,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> Optional[HealthServer]:
    """
    Spawns and starts the health check server using environment variables or configuration defaults.
    """
    server_host = host or os.getenv("HEALTH_SERVER_HOST", "0.0.0.0")
    server_port = int(port or os.getenv("HEALTH_SERVER_PORT", "8080"))

    server = HealthServer(bot=bot, host=server_host, port=server_port)
    await server.start()
    return server
