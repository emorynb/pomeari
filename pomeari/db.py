import os
from collections.abc import Iterable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, cast

import aiosqlite
import oschmod

from .types import PostLog, RunLog, XpostResult

# Default application data directory
DEFAULT_DATA_DIR = Path.home() / ".pomeari"

# Default SQLite database location
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "pomeari.db"


def prepare_data_dir(data_dir: Path = DEFAULT_DATA_DIR) -> Path:
    """Create the selected data directory and return its database path.

    On non-Windows systems, the data directory is restricted to mode
    ``0700``.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / DEFAULT_DB_PATH.name

    if os.name != "nt":
        oschmod.set_mode(str(data_dir), 0o700)

    return db_path


class Database:
    """Async SQLite persistence interface for Pomeari.

    Constructor accepts the database file ``path`` for testing/embedding.
    Operations generally open a fresh connection per each call.
    """

    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Async context manager for ``Database``.

        Use:

        ```py
        async with Database().connect() as db:
            ...
        ```
        """

        db = await aiosqlite.connect(self.path)
        await db.execute("PRAGMA foreign_keys = ON;")
        try:
            yield db
        finally:
            await db.close()

    async def initialize(self):
        """Execute the database initialization steps. Runs automatically when
        entering the ``connect`` context manager.

        The parent directory and schema tables are created if missing.

        On non-Windows systems, the database file created by this method is
        restricted to mode ``0600``.
        """

        self.path.parent.mkdir(parents=True, exist_ok=True)

        async with self.connect() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS run_log (
                    id INTEGER PRIMARY KEY,
                    caption TEXT NOT NULL
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS post_log (
                    rowid INTEGER PRIMARY KEY,
                    id INTEGER NOT NULL,
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
            await db.commit()

        if os.name != "nt":
            oschmod.set_mode(str(self.path), 0o600)

    async def set_config(self, key: str, value: str):
        """Create or replace a configuration entry."""

        async with self.connect() as db:
            await db.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
            await db.commit()

    async def remove_config(self, key: str):
        """Delete a configuration entry. An absent key gets safely ignored."""

        async with self.connect() as db:
            await db.execute("DELETE FROM config WHERE key = ?", (key,))
            await db.commit()

    async def clear_config(self):
        """Deletes every configuration entry."""

        async with self.connect() as db:
            await db.execute("DELETE FROM config")
            await db.commit()

    async def load_config(self) -> Mapping[str, str]:
        """Returns all stored configuration as a mapping of keys to values."""

        config = {}
        async with self.connect() as db:
            async with db.execute("SELECT key, value FROM config") as cursor:
                async for row in cursor:
                    config[row[0]] = row[1]
        return config

    async def next_run_id(self) -> int:
        """Increment and return the persisted run counter.

        An immediate SQLite transaction is used to serialize concurrent
        allocations. As such, the increment is atomic.
        """

        async with self.connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute("UPDATE run_counter SET last_run_id = last_run_id + 1")

            async with db.execute("SELECT last_run_id FROM run_counter") as cursor:
                row = await cursor.fetchone()

            await db.commit()
            if row is None:
                raise RuntimeError("Run counter is missing from the database.")
            return cast(int, row[0])

    async def log_run(self, run_id: int, caption: str):
        """Persist a publishing ``run_id`` and ``caption`` in the logs."""

        async with self.connect() as db:
            await db.execute(
                "INSERT INTO run_log (id, caption) VALUES (?, ?)",
                (run_id, caption),
            )
            await db.commit()

    async def log_post(
        self,
        run_id: int,
        platform_name: str,
        result: XpostResult,
    ):
        """Persist a ``result`` for ``platform_name`` within ``run_id``.

        If the passed ``XpostResult`` has no creation time, the current
        timestamp is supplied to the database entry.
        """

        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO post_log
                    (id, platform, url, created_at, metadata)
                VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
                """,
                (
                    run_id,
                    platform_name,
                    result.url,
                    result.created_at,
                    result.metadata,
                ),
            )
            await db.commit()

    async def get_post_logs(self, limit: int = 100) -> Iterable[Mapping[str, object]]:
        """Fetch low-level post-log mappings.

        Records are sorted by newest first. ``limit`` (100 by default) controls
        the amount of records returned.
        """

        async with self.connect() as db:
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

    async def get_run_logs(self, limit: int = 100) -> Mapping[int, str]:
        """Fetch low-level run-ID-to-caption mappings.

        Records are sorted by newest first. ``limit`` (100 by default) controls
        the amount of records returned.
        """

        async with self.connect() as db:
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

    async def get_history(self, limit: int = 100) -> Iterable[RunLog]:
        """Fetch recent publishing runs as ``RunLog`` objects.

        Runs are sorted newest first; posts inside each run retain the original
        insertion order. Runs with no successful logged posts are still
        included.
        """

        async with self.connect() as db:
            db.row_factory = aiosqlite.Row
            run_query = """
                SELECT id, caption
                FROM run_log
                ORDER BY id DESC
                LIMIT ?
            """
            async with db.execute(run_query, (limit,)) as cursor:
                run_rows = await cursor.fetchall()

            history = []
            for run_row in run_rows:
                post_query = """
                    SELECT platform, url, created_at, metadata
                    FROM post_log
                    WHERE id = ?
                    ORDER BY rowid
                """
                async with db.execute(post_query, (run_row["id"],)) as cursor:
                    post_rows = await cursor.fetchall()

                posts = []
                for post_row in post_rows:
                    posts.append(
                        PostLog(
                            platform=post_row["platform"],
                            url=post_row["url"],
                            created_at=post_row["created_at"],
                            metadata=post_row["metadata"],
                        )
                    )

                history.append(
                    RunLog(
                        id=run_row["id"],
                        caption=run_row["caption"],
                        posts=posts,
                    )
                )

            return history

    async def get_favorite_platform(self) -> str:
        """Fetch the persisted name of the favorite platform."""

        async with self.connect() as db:
            async with db.execute(
                "SELECT name FROM favorite_platform LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        "Favorite platform is missing from the database.\n"
                        "You need to set one up first:\n"
                        "    pomeari platform favorite telegraph"
                    )
                return cast(str, row[0])

    async def set_favorite_platform(self, name: str):
        """Store the supplied favorite platform name.

        Note that this method does not validate adapter availability;
        ``PomeariService`` performs that check instead.
        """

        async with self.connect() as db:
            await db.execute("UPDATE favorite_platform SET name = ?", (name,))
            await db.commit()

    async def clear_logs(self):
        """Delete all run and post history and reset the run counter to zero."""

        async with self.connect() as db:
            await db.execute("DELETE FROM post_log")
            await db.execute("DELETE FROM run_log")
            await db.execute("UPDATE run_counter SET last_run_id = 0")
            await db.commit()

    async def reset(self):
        """Delete the SQLite file and initialize a fresh database."""

        self.path.unlink(missing_ok=True)
        await self.initialize()
