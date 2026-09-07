import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database
from utils.config import config
from utils.logger import log, set_log_level
from utils.i18n import t, load_guild_translations
from utils.templates import ICON_SET_TEMPLATES, get_template_data, load_custom_sets, get_event_conf
from utils.presence import start_presence_task
from utils.health_server import start_health_server
from utils.metrics import metrics
from cogs.event_ui import DynamicEventView

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

class EventBot(commands.Bot):
    """Nexus Discord Event Management Bot."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix=config.command_prefix, intents=intents)
        self.config_obj = config
        self.master_guild_ids = config.master_guild_ids
        self.db_manager = database.db_manager
        self.db_pool = None
        self.presence_task = None
        self.health_server = None

    async def _init_database(self):
        """Initializes PostgreSQL connection pool, schema, and factory default templates."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            log.error("DATABASE_URL is not set in .env! Cannot start bot.")
            raise RuntimeError("DATABASE_URL is not set in .env! Cannot start bot.")

        min_size = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
        max_size = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
        command_timeout = float(os.getenv("DB_COMMAND_TIMEOUT", "30.0"))
        max_inactive = float(os.getenv("DB_MAX_INACTIVE_LIFETIME", "300.0"))
        acquire_timeout = float(os.getenv("DB_ACQUIRE_TIMEOUT", "10.0"))

        try:
            pool = await database.create_pool(
                dsn,
                min_size=min_size,
                max_size=max_size,
                command_timeout=command_timeout,
                max_inactive_connection_lifetime=max_inactive,
                timeout=acquire_timeout,
            )
            self.db_pool = pool
            await database.set_pool(pool)
            await database.init_db()
            log.info("Successfully connected to PostgreSQL with connection pool (min=%d, max=%d).", min_size, max_size)

            if self.master_guild_ids:
                for gid in self.master_guild_ids:
                    await load_guild_translations(gid)

            global_sets = await database.get_all_global_emoji_sets()
            if not global_sets:
                log.info("No global emoji sets in database. Seeding factory defaults from templates...")
                count = 0
                for tid, tmpl in ICON_SET_TEMPLATES.items():
                    name = t(tmpl.get("label_key"), guild_id=None) if "label_key" in tmpl else tid
                    data = get_template_data(tid)
                    if data:
                        await database.save_global_emoji_set(tid, name, data)
                        count += 1
                log.info("Seeded %d global emoji set(s) from templates.", count)
        except Exception as e:
            log.error("Failed to connect to PostgreSQL: %s", e)
            raise RuntimeError(f"Failed to initialize database: {e}") from e

    async def _load_extensions(self):
        """Loads global and master-restricted extension packages."""
        global_extensions = [
            "cogs.event_commands",
            "cogs.scheduler_task",
            "cogs.server_setup",
            "cogs.emoji_wizard",
            "cogs.attendance",
        ]
        master_extensions = [
            "cogs.master_commands",
        ]

        for ext in global_extensions:
            try:
                await self.load_extension(ext)
                log.info("Loaded extension: %s", ext)
            except Exception as e:
                log.error("Failed to load extension %s: %s", ext, e, exc_info=True)

        for ext in master_extensions:
            try:
                await self.load_extension(ext)
                log.info("Loaded master extension: %s", ext)
            except Exception as e:
                log.error("Failed to load master extension %s: %s", ext, e, exc_info=True)

        # Restrict master command group to configured master guilds
        if self.master_guild_ids:
            master_cog = self.get_cog("MasterCommands")
            if master_cog:
                self.tree.remove_command("master")
                for gid in self.master_guild_ids:
                    master_guild = discord.Object(id=gid)
                    self.tree.add_command(master_cog, guild=master_guild)
                log.info("Master Hub isolated to guilds: %s (Removed from Global)", self.master_guild_ids)

    async def _load_persistent_views(self):
        """Pre-loads custom emoji sets and re-attaches views for all active events."""
        await load_custom_sets()
        active_events = await database.get_active_events()
        for event in active_events:
            try:
                conf = get_event_conf(event['config_name'])
                view = DynamicEventView(self, event['event_id'], conf)
                await view.prepare()
                self.add_view(view)
            except Exception as e:
                log.error("Failed to load persistent view for event %s: %s", event.get('event_id'), e, guild_id=event.get('guild_id'))

    def _register_error_handler(self):
        """Registers the global application command error handler."""
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
            err_type = type(error).__name__
            metrics.record_error(err_type)
            if isinstance(error, discord.app_commands.CheckFailure):
                msg = t("ERR_ADMIN_ONLY", guild_id=interaction.guild_id)
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            else:
                log.error("[Error Handler] Unhandled error: %s", error, exc_info=True)
                clean_err = str(error.__cause__ or error)
                msg = t("ERR_WIZARD_GENERAL", guild_id=interaction.guild_id, e=clean_err)
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(msg, ephemeral=True)
                    else:
                        await interaction.response.send_message(msg, ephemeral=True)
                except Exception:
                    pass

    async def setup_hook(self):
        """Asynchronous setup lifecycle hook called before the bot connects to Gateway."""
        set_log_level(config.get("globals", {}).get("logging_level", "INFO"))
        await self._init_database()
        await self._load_extensions()
        await self._load_persistent_views()
        self._register_error_handler()
        
        # Start dynamic presence rotation background worker
        self.presence_task = start_presence_task(self)

        # Start lightweight HTTP liveness, readiness, and metrics server
        self.health_server = await start_health_server(self)
        log.info("Setup complete. Manual sync available via /master system sync.")

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "Unknown")
        log.info("Nexus Event Bot is ready and monitoring events.")
        log.info("------")

    async def close(self):
        """Gracefully closes database connection pool, background tasks, and discord client connection."""
        log.info("Shutting down Nexus Event Bot...")
        if self.presence_task and not self.presence_task.done():
            self.presence_task.cancel()
            try:
                await self.presence_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.health_server:
            await self.health_server.stop()
            self.health_server = None
        await self.db_manager.close()
        await super().close()

if __name__ == "__main__":
    if not TOKEN:
        log.critical("BOT_TOKEN is not set in .env! Cannot start bot.")
        raise SystemExit(1)
        
    bot = EventBot()
    try:
        bot.run(TOKEN)
    except (KeyboardInterrupt, SystemExit):
        log.info("Nexus Event Bot terminated cleanly.")
    except Exception as exc:
        log.critical("Fatal error during bot execution: %s", exc, exc_info=True)
        raise SystemExit(1)
