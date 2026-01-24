from pathlib import Path
from typing import Any

import aiosqlite
import oschmod

from .types import XpostResult

# a local path is used for the DB intentionally, and yes, one of those
# intentions is that the API secrets and whatever else that may be found there
# essentially in plain text are kept local in the user's home catalogue and
# hopefully kept just as secret as any other sensitive info they may have there.
DB_PATH = Path.home() / ".pomeari.db"


async def init_db():
    """
    Initialize the DB with tables and the `run_id` counter.

    Only has to be ran once before any other DB operations are done, and it's
    not on the helpers to ensure they're called, but on the one calling the
    helpers.
    """
    oschmod.set_mode(str(DB_PATH), 0o600)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            id INTEGER PRIMARY KEY, -- run_id
            caption TEXT NOT NULL
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS post_log (
            rowid INTEGER PRIMARY KEY,
            id INTEGER NOT NULL, -- run_id
            platform TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '',
            FOREIGN KEY (id)
            REFERENCES run_log(id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS run_counter (
            last_run_id INTEGER NOT NULL
        );
        """)
        await db.execute("""
        INSERT INTO run_counter (last_run_id)
        SELECT 0
        WHERE NOT EXISTS (SELECT 1 FROM run_counter);
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS favorite_platform (
            name TEXT NOT NULL
        );
        """)
        await db.execute("""
        INSERT INTO favorite_platform (name)
        SELECT 'mastodon'
        WHERE NOT EXISTS (SELECT 1 FROM favorite_platform);
        """)

        await db.commit()


async def set_conf(key: str, value: str):
    """
    Add an entry to the config table or modify it.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()


async def rm_conf(key: str):
    """
    Remove an entry from the config table by key.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM config WHERE key = ?", (key,))
        await db.commit()


async def load_config() -> dict[str, str]:
    """
    Load the config table from DB as a dict.

    WARNING: remember that it contains API secrets! This is raw data and
    shouldn't be passed around without stripping what's unwanted.
    """
    config = {}
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM config") as cursor:
            async for row in cursor:
                config[row[0]] = row[1]
    return config


async def inc_and_get_run_id() -> int:
    """
    Increment and return the new `run_id` to then pass to `log_post`.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN")

        await db.execute("UPDATE run_counter SET last_run_id = last_run_id + 1")

        async with db.execute("SELECT last_run_id FROM run_counter") as cursor:
            row = await cursor.fetchone()

        await db.commit()
        return row[0]  # pyright: ignore


async def log_run(run_id: int, caption: str):
    """
    Log the current crossposting run in the DB.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO run_log (id, caption) VALUES (?, ?)",
            (run_id, caption),
        )
        await db.commit()


async def log_post(run_id: int, platform_name: str, result: XpostResult):
    """
    Log what has just been crossposted (to where, and optionally how) in the DB.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO post_log (id, platform, url, created_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                run_id,
                platform_name,
                result.url,
                result.created_at,
                result.metadata,
            ),
        )
        await db.commit()


async def get_post_logs(limit: int = 100) -> list[dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT rowid, id, platform, url, created_at, metadata
            FROM post_log
            ORDER BY rowid DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_run_logs(limit: int = 100) -> dict[int, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT id, caption
            FROM run_log
            ORDER BY id DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return {row["id"]: row["caption"] for row in rows}


async def get_favorite_platform() -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM favorite_platform LIMIT 1") as cur:
            row = await cur.fetchone()
            return row[0]  # pyright: ignore


async def set_favorite_platform(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE favorite_platform SET name = ?", (name,))
        await db.commit()
