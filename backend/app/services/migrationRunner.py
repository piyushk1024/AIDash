import logging
from pathlib import Path
import asyncpg

logger = logging.getLogger(__name__)

# backend/app/services/ -> backend/app/ -> backend/ -> backend/db/migrations/
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "db" / "migrations"

MIGRATION_LOCK_KEY = 8261025  # arbitrary fixed int64 key for advisory lock

async def run_migrations(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_KEY)
        try:
            await _run_migrations_locked(conn)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_KEY)


async def _run_migrations_locked(conn: asyncpg.Connection) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_versions (
            version     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            applied_at  TIMESTAMP DEFAULT NOW()
        )
    """)

    applied = {
        row["version"]
        for row in await conn.fetch("SELECT version FROM schema_versions")
    }

    migration_files = sorted(
        MIGRATIONS_DIR.glob("*.sql"),
        key=lambda f: int(f.name.split("_")[0]),
    )

    pending = [f for f in migration_files if int(f.name.split("_")[0]) not in applied]

    if not pending:
        logger.info("Migrations: all %d applied, nothing to run.", len(migration_files))
        return

    for path in pending:
        version = int(path.name.split("_")[0])
        async with conn.transaction():
            await conn.execute(path.read_text())
            await conn.execute(
                "INSERT INTO schema_versions (version, name) VALUES ($1, $2)",
                version, path.name,
            )
        logger.info("Migration applied: %s", path.name)

    logger.info("Migrations: %d new migration(s) applied.", len(pending))