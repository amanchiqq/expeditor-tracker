"""Apply versioned SQL migrations. Run from the repository root."""
import asyncio
import hashlib
import os
from pathlib import Path
import asyncpg


async def migrate():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(731095124)")
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            for path in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
                sql = path.read_text(encoding="utf-8-sig")
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                previous = await conn.fetchval("SELECT checksum FROM schema_migrations WHERE name=$1", path.name)
                if previous is not None:
                    if previous != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    continue
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations(name, checksum) VALUES($1,$2)", path.name, checksum)
                print(f"Applied {path.name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
