# Nexus Discord Event Bot

[![Python Version](https://img.shields.io/badge/python-3.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-v2.6%2B-5865F2.svg)](https://github.com/Rapptz/discord.py)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-289%20passed-brightgreen.svg)](tests/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED.svg)](Dockerfile)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-orange.svg)](.github/workflows/ci.yml)

Enterprise-grade Discord event and attendance orchestration platform designed for gaming communities, esports tournaments, and organizational servers. Built on discord.py and asyncpg, Nexus delivers atomic concurrency control, PostgreSQL row-level locking, automated reminder dispatching, Prometheus observability, and container orchestration readiness.

<p align="center">
  <img src="assets/event_card_preview.png" alt="Nexus Event Card Preview" width="650"/>
</p>

---

## Architectural Highlights

- Concurrency and Transaction Safety: Employs PostgreSQL row-level locks (`SELECT ... FOR UPDATE`) during RSVP submissions to prevent race conditions and event overbooking under high concurrent load.
- Referential Integrity: Database schema enforces foreign key constraints with `ON DELETE CASCADE`, guaranteeing clean cascade deletions without orphaned records.
- Asynchronous Non-Blocking Workers: Event evaluations and notifications execute concurrently using bounded semaphores to prevent event-loop starvation and respect Discord REST API rate limits.
- Bounded Self-Evicting Cache: In-memory LRU TTL caches prevent memory leaks across cooldowns, guild configurations, and translation layers.
- Observability and Container Readiness: Built-in asynchronous HTTP server exposes Prometheus metrics (`/metrics`), liveness probes (`/healthz`), and readiness probes (`/readyz`).
- Hardened Production Container: Multi-stage slim Docker image executing under a non-privileged user with automated container healthcheck directives.

---

## Core Capabilities

### 1. Event Lifecycle and Wizard
- Interactive modal and view wizard for single events, recurring event series, and fill-to-start lobbies.
- Intelligent recurrence engine supporting daily, weekly, monthly, interval-based schedules, and custom day-of-week selections.
- Configurable post-event grace periods (default 12 hours) allowing organizers and attendees to audit attendance before archival.
- Fallback channel resolution ensuring recurring events are never dropped due to cold client-side caches.

### 2. RSVP and Roster Management
- Flexible RSVP states: accepted, tentative, declined, and automated waiting lists.
- Role-based limits and tier-based registration restrictions.
- Atomic waiting list promotions when accepted slots open.
- Temporary Discord role generation and assignment for participants, with graceful cleanup on event conclusion.

### 3. Multi-Slot Reminder Dispatching
- Up to 5 customizable reminder slots per event.
- Granular delivery methods: channel ping, direct message (DM), or hybrid.
- Non-blocking parallel DM dispatching throttled via semaphores to avoid Discord 429 rate limits.
- Safe template formatting preventing denial-of-service vulnerabilities.

### 4. Attendance and Reliability Auditing
- Real-time interactive attendance views for event organizers.
- Attendance verification toggles (`present` vs `no_show`).
- Global and guild-level member reliability scores and no-show statistics.
- Export capabilities for external auditing and record-keeping.

### 5. Internationalization (i18n)
- Dynamic multi-language localization system with fallback chains.
- Per-guild custom translation overrides stored in PostgreSQL.
- Cached configuration layer with automatic cache invalidation upon configuration updates and server resets.

---

## Observability and Healthcheck Endpoints

Nexus includes an asynchronous HTTP service powered by `aiohttp.web` running on port `8080` (configurable via `HEALTH_SERVER_PORT`).

| Endpoint | Method | Purpose | Response |
| :--- | :--- | :--- | :--- |
| `/healthz` | GET | Liveness probe for Docker and Kubernetes | HTTP 200 with uptime and service status |
| `/readyz` | GET | Readiness probe checking Gateway and Database | HTTP 200 if healthy, HTTP 503 if degraded |
| `/metrics` | GET | Prometheus scraper endpoint | Standard Prometheus text exposition (`text/plain; version=0.0.4`) |
| `/` | GET | Diagnostic index and service metadata | JSON payload with active endpoints |

### Exposed Prometheus Metrics
- `nexus_uptime_seconds`: Total runtime of the bot in seconds.
- `nexus_gateway_latency_seconds`: Discord WebSocket heartbeat latency.
- `nexus_guilds_count`: Total connected Discord guilds.
- `nexus_cached_users_count`: Total users cached in client memory.
- `nexus_active_events_count`: Active events stored in the database.
- `nexus_db_total_rsvps`: Total RSVP records in database.
- `nexus_db_pool_size` / `nexus_db_pool_free`: PostgreSQL connection pool utilization.
- `nexus_commands_total{command, status}`: Counter of executed application commands.
- `nexus_errors_total{type}`: Counter of caught application errors.
- `nexus_reminders_dispatched_total{method}`: Counter of dispatched reminders.
- `nexus_rsvps_action_total{status}`: Counter of user RSVP actions.

---

## Quick Start with Docker Compose

The fastest way to deploy Nexus in production is via Docker Compose:

### 1. Clone Repository
```bash
git clone https://github.com/stargate91/discord-event-bot.git
cd discord-event-bot
```

### 2. Configure Environment
Create a `.env` file from the provided example:
```bash
cp .env.example .env
```
Edit `.env` and set your credentials:
```env
BOT_TOKEN=your_discord_bot_token_here
POSTGRES_USER=nexus
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=discord_events
```

### 3. Launch Services
```bash
docker compose up -d
```

### 4. Verify Health Status
```bash
docker compose ps
curl -f http://localhost:8080/readyz
```

---

## Manual Local Installation

### Prerequisites
- Python 3.12 or later
- PostgreSQL 16 server
- Git

### Installation Steps

1. Clone the repository and navigate into the directory:
   ```bash
   git clone https://github.com/stargate91/discord-event-bot.git
   cd discord-event-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install production dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Configure the environment variables in `.env`:
   ```env
   BOT_TOKEN=your_discord_bot_token_here
   DATABASE_URL=postgresql://nexus:password@localhost:5432/discord_events
   HEALTH_SERVER_PORT=8080
   HEALTH_SERVER_HOST=0.0.0.0
   ```

5. Run the bot:
   ```bash
   python main.py
   ```
   Database migrations (`001_initial_schema.sql`, `002_cascade_foreign_keys_and_types.sql`) are applied automatically on startup.

---

## Configuration Reference

Nexus reads server and feature settings from `config.json` and PostgreSQL `guild_settings`.

```json
{
  "command_prefix": "!",
  "language": "hu",
  "master_guild_ids": [],
  "globals": {
    "logging_level": "INFO",
    "health_server": {
      "enabled": true,
      "port": 8080,
      "host": "0.0.0.0"
    }
  }
}
```

---

## Testing and Quality Assurance

The test suite covers unit logic, concurrency safety, cache invalidation, API rate-limiting semaphores, and live PostgreSQL integrations.

### Run Automated Tests
```bash
# Run complete test suite with coverage
python -m pytest -v --cov=. --cov-report=term-missing
```

### Run Static Analysis and Linter
```bash
# Run Ruff linting across entire project
python -m ruff check cogs database services utils tests main.py
```

### Run Real PostgreSQL Integration Tests
To execute end-to-end database tests against a live PostgreSQL instance:
```bash
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test_db python -m pytest tests/test_real_postgres_integration.py
```

---

## CI/CD Pipeline

Continuous integration is orchestrated via GitHub Actions (`.github/workflows/ci.yml`):
- `lint-and-test`: Spins up an automated `postgres:16-alpine` service container, executes `ruff check`, and runs the full `pytest` suite with live PostgreSQL migrations and concurrency tests.
- `docker-build`: Builds and validates the production Docker image against container specifications.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
