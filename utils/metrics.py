import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional
import discord


class MetricsRegistry:
    """
    In-memory metrics collector and exporter formatted for Prometheus scraping.
    Provides standard Prometheus exposition text (text/plain; version=0.0.4).
    """

    def __init__(self) -> None:
        self.start_time: float = time.time()
        self._command_counts: Dict[tuple[str, str], int] = defaultdict(int)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._reminder_counts: Dict[str, int] = defaultdict(int)
        self._rsvp_counts: Dict[str, int] = defaultdict(int)

    def record_command(self, command: str, status: str = "success") -> None:
        """Records a command invocation with outcome status."""
        self._command_counts[(command, status)] += 1

    def record_error(self, error_type: str) -> None:
        """Records an unhandled or handled application error."""
        self._error_counts[error_type] += 1

    def record_reminder_sent(self, method: str) -> None:
        """Records a notification or reminder dispatch."""
        self._reminder_counts[method] += 1

    def record_rsvp(self, status: str) -> None:
        """Records an RSVP action."""
        self._rsvp_counts[status] += 1

    @property
    def uptime_seconds(self) -> float:
        """Returns bot uptime in seconds."""
        return max(0.0, time.time() - self.start_time)

    async def generate_prometheus_metrics(
        self,
        bot: Optional[discord.Client] = None,
        db_stats: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Builds a standard Prometheus metrics exposition payload.
        """
        lines: List[str] = []

        # 1. Info Metric
        lines.append("# HELP nexus_info Bot metadata and environment info.")
        lines.append("# TYPE nexus_info gauge")
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        dc_ver = getattr(discord, "__version__", "unknown")
        lines.append(
            f'nexus_info{{version="1.0.0",python_version="{py_ver}",discord_version="{dc_ver}"}} 1'
        )

        # 2. Uptime
        lines.append("# HELP nexus_uptime_seconds Total time the bot has been running.")
        lines.append("# TYPE nexus_uptime_seconds gauge")
        lines.append(f"nexus_uptime_seconds {self.uptime_seconds:.2f}")

        # 3. Discord Gateway Latency & Guilds
        if bot is not None:
            latency = bot.latency if hasattr(bot, "latency") and bot.latency is not None else 0.0
            # Discord.py returns latency in seconds or float('inf') when disconnected
            if latency == float("inf") or latency != latency:  # Check for inf/NaN
                latency = 0.0
            guild_count = len(bot.guilds) if hasattr(bot, "guilds") else 0
            user_count = len(bot.users) if hasattr(bot, "users") else 0

            lines.append("# HELP nexus_gateway_latency_seconds Discord WebSocket heartbeat latency.")
            lines.append("# TYPE nexus_gateway_latency_seconds gauge")
            lines.append(f"nexus_gateway_latency_seconds {latency:.4f}")

            lines.append("# HELP nexus_guilds_count Number of connected Discord servers.")
            lines.append("# TYPE nexus_guilds_count gauge")
            lines.append(f"nexus_guilds_count {guild_count}")

            lines.append("# HELP nexus_cached_users_count Number of users in Discord client cache.")
            lines.append("# TYPE nexus_cached_users_count gauge")
            lines.append(f"nexus_cached_users_count {user_count}")

        # 4. Database Statistics
        if db_stats is not None:
            active_events = db_stats.get("events", 0)
            total_rsvps = db_stats.get("rsvps", 0)
            guild_settings_count = db_stats.get("guilds", 0)

            lines.append("# HELP nexus_active_events_count Total number of active scheduled events in database.")
            lines.append("# TYPE nexus_active_events_count gauge")
            lines.append(f"nexus_active_events_count {active_events}")

            lines.append("# HELP nexus_db_total_rsvps Total RSVPs recorded in database.")
            lines.append("# TYPE nexus_db_total_rsvps gauge")
            lines.append(f"nexus_db_total_rsvps {total_rsvps}")

            lines.append("# HELP nexus_configured_guilds_count Total guilds with database configurations.")
            lines.append("# TYPE nexus_configured_guilds_count gauge")
            lines.append(f"nexus_configured_guilds_count {guild_settings_count}")

        # 5. Database Connection Pool Metrics
        try:
            import database
            if hasattr(database, "db_manager") and database.db_manager.is_initialized:
                pool = database.db_manager.get_pool()
                size = getattr(pool, "_size", 0)
                free_size = len(getattr(pool, "_holders", []))
                lines.append("# HELP nexus_db_pool_size Total connections in asyncpg connection pool.")
                lines.append("# TYPE nexus_db_pool_size gauge")
                lines.append(f"nexus_db_pool_size {size}")

                lines.append("# HELP nexus_db_pool_free Available idle connections in asyncpg connection pool.")
                lines.append("# TYPE nexus_db_pool_free gauge")
                lines.append(f"nexus_db_pool_free {free_size}")
        except Exception:
            pass

        # 6. Counters
        lines.append("# HELP nexus_commands_total Total number of command executions.")
        lines.append("# TYPE nexus_commands_total counter")
        if self._command_counts:
            for (cmd, status), count in self._command_counts.items():
                lines.append(f'nexus_commands_total{{command="{cmd}",status="{status}"}} {count}')
        else:
            lines.append('nexus_commands_total{command="none",status="none"} 0')

        lines.append("# HELP nexus_errors_total Total number of application errors.")
        lines.append("# TYPE nexus_errors_total counter")
        if self._error_counts:
            for err_type, count in self._error_counts.items():
                lines.append(f'nexus_errors_total{{type="{err_type}"}} {count}')
        else:
            lines.append('nexus_errors_total{type="none"} 0')

        lines.append("# HELP nexus_reminders_dispatched_total Total reminders dispatched.")
        lines.append("# TYPE nexus_reminders_dispatched_total counter")
        if self._reminder_counts:
            for method, count in self._reminder_counts.items():
                lines.append(f'nexus_reminders_dispatched_total{{method="{method}"}} {count}')
        else:
            lines.append('nexus_reminders_dispatched_total{method="none"} 0')

        lines.append("# HELP nexus_rsvps_action_total Total RSVP actions performed by users.")
        lines.append("# TYPE nexus_rsvps_action_total counter")
        if self._rsvp_counts:
            for status, count in self._rsvp_counts.items():
                lines.append(f'nexus_rsvps_action_total{{status="{status}"}} {count}')
        else:
            lines.append('nexus_rsvps_action_total{status="none"} 0')

        return "\n".join(lines) + "\n"


# Global metrics registry singleton
metrics = MetricsRegistry()
