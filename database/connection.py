from typing import Optional, AsyncIterator
from contextlib import asynccontextmanager
import re
from pathlib import Path
import asyncpg
from utils.logger import log

DEFAULT_TIMEZONE: str = 'UTC'
MAX_EVENT_REMINDERS: int = 5
MIGRATIONS_DIR: Path = Path(__file__).parent / "migrations"


class DatabaseManager:
    """
    Manages PostgreSQL connection pool lifecycle, transactions, and migrations.
    Encapsulates connection state and supports dependency injection and test mocking.
    """

    def __init__(self, pool: Optional[asyncpg.Pool] = None) -> None:
        self._pool: Optional[asyncpg.Pool] = pool

    @property
    def is_initialized(self) -> bool:
        """Returns True if the database pool has been created and assigned."""
        return self._pool is not None

    def set_pool(self, pool: asyncpg.Pool) -> None:
        """Assigns the active asyncpg connection pool."""
        self._pool = pool

    def get_pool(self) -> asyncpg.Pool:
        """Returns the active pool, raising RuntimeError if not initialized."""
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized. Call init_database() first.")
        return self._pool

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquires a connection from the pool as an async context manager."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            yield conn

    async def close(self) -> None:
        """Gracefully closes all connections in the pool."""
        if self._pool:
            log.info("Closing PostgreSQL connection pool...")
            await self._pool.close()
            self._pool = None
            log.info("PostgreSQL connection pool closed.")

    async def run_migrations(self, conn: Optional[asyncpg.Connection] = None) -> None:
        """Discovers and applies pending SQL migrations in atomic transactions."""
        if conn is not None:
            await self._execute_migrations(conn)
        else:
            async with self.acquire() as connection:
                await self._execute_migrations(connection)

    async def _execute_migrations(self, conn: asyncpg.Connection) -> None:
        # 1. Ensure schema_migrations table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # 2. Fetch already applied versions
        rows = await conn.fetch("SELECT version FROM schema_migrations")
        applied_versions = {int(r["version"]) for r in rows}

        # 3. Discover migration files
        if not MIGRATIONS_DIR.exists():
            log.warning("Migrations directory not found: %s", MIGRATIONS_DIR)
            return

        migration_files: list[tuple[int, str, Path]] = []
        for file_path in MIGRATIONS_DIR.glob("*.sql"):
            match = re.match(r"^(\d+)_(.+)\.sql$", file_path.name)
            if match:
                version = int(match.group(1))
                name = match.group(2)
                migration_files.append((version, name, file_path))

        # Sort migrations sequentially by version
        migration_files.sort(key=lambda x: x[0])

        # 4. Apply pending migrations in atomic transactions
        for version, name, file_path in migration_files:
            if version not in applied_versions:
                log.info("[DB Migration] Applying migration %03d_%s...", version, name)
                sql_content = file_path.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql_content)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                        version,
                        name,
                    )
                log.info("[DB Migration] Successfully applied migration %03d_%s.", version, name)


# Global singleton instance for bot runtime and repository delegation
db_manager = DatabaseManager()


async def create_pool(
    dsn: str,
    min_size: int = 5,
    max_size: int = 20,
    command_timeout: float = 30.0,
    max_inactive_connection_lifetime: float = 300.0,
    timeout: float = 10.0,
) -> asyncpg.Pool:
    """Creates and configures a tuned asyncpg connection pool."""
    return await asyncpg.create_pool(
        dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        max_inactive_connection_lifetime=max_inactive_connection_lifetime,
        timeout=timeout,
    )


async def set_pool(pool: asyncpg.Pool) -> None:
    """Assigns the global database connection pool."""
    db_manager.set_pool(pool)


async def get_pool() -> asyncpg.Pool:
    """Returns the initialized database connection pool."""
    return db_manager.get_pool()


async def init_db() -> None:
    """Initializes database schema and executes all pending migrations."""
    await db_manager.run_migrations()
    log.info("Database schema initialized and up-to-date.")
