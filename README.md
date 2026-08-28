# Nexus Discord Event Bot

Nexus is a modular, enterprise-grade Discord event management bot built with Python 3, `discord.py`, and PostgreSQL. It provides an interactive UI-driven workflow for scheduling events, managing recurring series, coordinating fill-to-start lobbies, tracking RSVPs and attendance, auditing reliability, and exporting data to standard formats like CSV and iCalendar.

---

## Key Features

- **Interactive Event Wizard:** Visual creation and editing modal workflow for single events, recurring event series, and fill-to-start lobbies without memorizing complex syntax.
- **Dynamic RSVP System:** Real-time event embed updates with configurable capacity caps, waitlists, temporary role assignments upon signup, and role-based signup restrictions.
- **Multi-Slot Automated Reminders:** Configure up to 5 reminder slots per event with customizable offsets, delivery methods (channel ping or direct message), and targeted recipient groups (confirmed attendees, waitlist, etc.).
- **Fill-to-Start Lobbies:** Create time-flexible lobbies that notify organizers or automatically activate when the target participant count is reached.
- **Recurring Series Management:** Native recurrence engine supporting daily, weekly, bi-weekly, and monthly intervals with rolling automatic reposts and occurrence limits.
- **Attendance & Reliability Audits:** Mark post-event participant presence (Present, Late, No-Show) and generate guild-level reliability metrics and no-show audit leaderboards.
- **Data Exporting:** Export guild event history and participant RSVP records to CSV (optimized for Google Sheets / Excel) and future schedules to iCalendar (.ics) files.
- **Draft Management:** Automatically save in-progress event configurations and resume them at any time.
- **Customizable Branding & Emojis:** Per-server and global custom emoji sets for status indicators, buttons, and embeds.
- **Multi-Language Support (i18n):** Native support for English and Hungarian, with in-Discord override wizards for custom server strings.
- **Visual Server Administration:** Interactive `/setup` console for configuring server-wide defaults, channels, roles, timezones, and templates.
- **Master Operations Hub:** Isolated administrative controls for bot operators to inspect global database metrics, control presence rotations, and manage system-wide assets.

---

## Technology Stack

- **Runtime:** Python 3.10+ / 3.11+
- **Discord Framework:** `discord.py` (v2.6+)
- **Database:** PostgreSQL with `asyncpg` for asynchronous connection pooling
- **Configuration:** JSON with comments (`JSONC`) and `.env` environment variables
- **Timezone & Date Processing:** `python-dateutil`

---

## Project Structure

```text
nexus/
├── cogs/
│   ├── attendance/        # Attendance marking and tracking views
│   ├── emoji_wizard/      # Visual emoji set customization
│   ├── event_commands/    # Primary user and administrative event commands
│   ├── event_ui/          # Persistent dynamic embeds and interaction views
│   ├── event_wizard/      # Multi-step event creation and editing wizard
│   ├── master_commands/   # Isolated bot-owner global operations
│   ├── message_wizard/    # Visual translation and string customization
│   ├── scheduler_task/    # Background workers for reminders, recurrence, and lifecycle
│   └── server_setup/      # Interactive server configuration dashboard
├── database/
│   ├── migrations/        # SQL migration scripts (001_initial_schema.sql)
│   ├── repositories/      # Domain-specific async database access layers
│   ├── connection.py      # AsyncPG connection pool management
│   └── __init__.py        # Database manager interface
├── locales/               # Localization strings (en.json, hu.json, templates)
├── services/              # Core business logic services
│   ├── attendance_service.py
│   ├── event_service.py
│   ├── export_service.py
│   ├── notification_service.py
│   └── recurrence_service.py
├── utils/                 # Utility modules (auth, config, i18n, logger, presence, etc.)
├── config.example.json    # Bot configuration template
├── .env.example           # Environment variables template
├── requirements.txt       # Production dependencies
└── main.py                # Bot application entrypoint and lifecycle coordinator
```

---

## Prerequisites

Before setting up the bot, ensure you have:

1. **Python 3.10 or higher** installed.
2. **PostgreSQL 14 or higher** running locally or on a remote host.
3. A **Discord Bot Application** created in the [Discord Developer Portal](https://discord.com/developers/applications) with the following Privileged Gateway Intents enabled:
   - **Server Members Intent**
   - **Message Content Intent**

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/stargate91/discord-event-bot.git
cd discord-event-bot
```

### 2. Create and Activate a Virtual Environment

On Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
# Discord Bot Authentication Token
BOT_TOKEN=your_discord_bot_token_here

# PostgreSQL Database Connection URL
DATABASE_URL=postgresql://username:password@localhost:5432/discord_events

# Optional Master Guild IDs (comma-separated, enables /master commands)
MASTER_GUILD_IDS=123456789012345678

# Optional Premium Guild IDs (comma-separated)
PREMIUM_GUILD_IDS=123456789012345678
```

### 5. Configure Bot Settings

Copy `config.example.json` to `config.json`:

```bash
cp config.example.json config.json
```

Adjust the configuration file parameters as needed:

```json
{
  "master_guild_ids": [],
  "premium_guild_ids": [],
  "language": "en",
  "command_prefix": "!",
  "command_suffix": "",
  "globals": {
    "logging_level": "INFO",
    "wizard_timeout": 600,
    "version": "v2.2.0"
  }
}
```

### 6. Database Initialization

Database tables, constraints, and indexes are automatically initialized and migrated when the bot boots for the first time via `main.py` and `database/migrations/001_initial_schema.sql`.

### 7. Run the Bot

```bash
python main.py
```

---

## Command Reference

### Event Management (`/event`)

| Command | Description | Access |
| --- | --- | --- |
| `/event create` | Opens the interactive wizard to design and schedule a new event or recurring series. | Admin |
| `/event lobby` | Opens the creation wizard configured for fill-to-start lobbies. | Admin |
| `/event edit <event_id>` | Opens the wizard to edit an existing event or series. | Admin |
| `/event list` | Displays all currently active events in the server. | Admin |
| `/event cancel <event_id>` | Marks an event as cancelled and updates the message embed. | Admin |
| `/event postpone <event_id>` | Postpones an event to a new date/time with optional attendee notification. | Admin |
| `/event activate <event_id>` | Re-activates a previously cancelled or postponed event. | Admin |
| `/event remove <event_id>` | Deletes the event embed and cleans up associated roles and records. | Admin |
| `/event end <event_id>` | Manually closes an active event and archives it into past history. | Admin |
| `/event sheets` | Exports server event summaries and RSVP records as CSV files. | Admin |
| `/event ics` | Generates a standard `.ics` iCalendar file of all upcoming server events. | Everyone |
| `/event my-events` | Interactive menu listing events you are organizing or attending. | Everyone |
| `/event history` | View your personal past event attendance record. | Everyone |

### Server Administration & Auditing

| Command | Description | Access |
| --- | --- | --- |
| `/setup` | Opens the visual configuration dashboard to manage server defaults, channels, timezones, and roles. | Admin |
| `/admin check no-show` | Generates reliability reports for a specific event or a server-wide no-show leaderboard. | Admin |
| `/admin messages` | Opens the string customization wizard to override bot messages and translations. | Admin |
| `/admin emojis` | Customizes button and status indicator emoji sets for the server. | Admin |
| `/attendance manage <event_id>` | Interactive interface to mark attendees as Present, Late, or No-Show. | Admin |

### Event Drafts (`/draft`)

| Command | Description | Access |
| --- | --- | --- |
| `/draft continue <draft_id>` | Resumes a previously saved event creation session. | Everyone |
| `/draft delete <draft_id>` | Deletes a saved draft. | Everyone |
| `/draft delete-all` | Clears all saved drafts belonging to the user in the server. | Everyone |

### Master Administration (`/master`)

*Note: These commands are only available in guilds configured under `master_guild_ids`.*

| Command | Description | Access |
| --- | --- | --- |
| `/master stats` | Shows global operational stats: active guilds, events, RSVPs, latency, and system versions. | Bot Master |
| `/master status` | Visual console to configure dynamic rotating bot presence messages. | Bot Master |
| `/master global-sets` | Manage default emoji sets available across all servers. | Bot Master |
| `/master reset-global-sets` | Restores global emoji sets to factory code defaults. | Bot Master |

### Legacy Prefix Commands

| Command | Description | Access |
| --- | --- | --- |
| `!sync [guild\|global\|copy]` | Synchronizes slash application commands with the Discord API. | Bot Master |
| `!clear_commands` | Clears and resyncs command trees in case of registration conflicts. | Bot Master |

---

## Configuration Details

### `config.json` Options

- **`master_guild_ids`** (array of strings): Discord Guild IDs where master-only commands (`/master`) should be registered.
- **`premium_guild_ids`** (array of strings): Discord Guild IDs with premium tier limits.
- **`language`** (string): Default fallback language code (`"en"` for English, `"hu"` for Hungarian).
- **`command_prefix`** (string): Prefix used for text fallback and maintenance commands (default: `!` ).
- **`command_suffix`** (string): Optional suffix appended to slash command names (useful when running development and staging instances alongside each other).
- **`globals.logging_level`** (string): Log verbosity level (`"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"`).
- **`globals.wizard_timeout`** (integer): Timeout in seconds for interactive UI wizard sessions (default: `600`).
- **`globals.version`** (string): Version identifier displayed in status embeds and master telemetry.

---

## Background Workers & Scheduler

The bot includes an asynchronous scheduler cog (`cogs.scheduler_task`) running at regular intervals to handle automated tasks:

1. **Reminder Dispatcher:** Periodically scans for due reminder slots and sends configured channel mentions or direct messages.
2. **Event Lifecycle Monitor:** Automatically updates event statuses when start times are reached and transitions finished events to history.
3. **Recurring Series Generator:** Detects when recurring events finish and automatically posts the next scheduled occurrence based on configured recurrence intervals and offsets.
4. **Temporary Role Cleanup:** Removes temporary event participant roles after events conclude.
5. **Rotating Presence Engine:** Updates the bot's Discord activity text based on active event statistics or customized status presets.

---

## Localization (i18n)

Nexus includes a robust localization architecture:
- Core language catalogs are stored in `locales/en.json` (English) and `locales/hu.json` (Hungarian).
- Servers can configure their preferred language using `/setup`.
- Individual text strings and embeds can be customized per-guild using `/admin messages`.
- Contextual formatting supports dynamic interpolation for timestamps, counts, titles, and error reasons.

