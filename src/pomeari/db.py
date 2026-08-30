import os
import shutil
from collections.abc import Iterable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
import oschmod

from .types import PostLog, RunLog, XpostResult

DEFAULT_DATA_DIR = Path.home() / ".pomeari"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "pomeari.db"
LEGACY_DB_PATH = Path.home() / ".pomeari.db"


def prepare_data_directory(
    data_dir: Path = DEFAULT_DATA_DIR,
    legacy_path: Path | None = LEGACY_DB_PATH,
) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / DEFAULT_DB_PATH.name

    if not db_path.exists() and legacy_path and legacy_path.exists():
        temp_path = db_path.with_suffix(".db.migrating")
        shutil.copy2(legacy_path, temp_path)
        temp_path.replace(db_path)

    if os.name != "nt":
        oschmod.set_mode(str(data_dir), 0o700)

    return db_path


class Database:
    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.path)
        await db.execute("PRAGMA foreign_keys = ON;")
        try:
            yield db
        finally:
            await db.close()

    async def initialize(self):
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
            await db.execute("""
                INSERT INTO favorite_platform (name)
                SELECT 'mastodon'
                WHERE NOT EXISTS (SELECT 1 FROM favorite_platform);
            """)
            await db.commit()

        if os.name != "nt":
            oschmod.set_mode(str(self.path), 0o600)

    async def set_config(self, key: str, value: str):
        async with self.connect() as db:
            await db.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
            await db.commit()

    async def remove_config(self, key: str):
        async with self.connect() as db:
            await db.execute("DELETE FROM config WHERE key = ?", (key,))
            await db.commit()

    async def clear_config(self):
        async with self.connect() as db:
            await db.execute("DELETE FROM config")
            await db.commit()

    async def load_config(self) -> Mapping[str, str]:
        config = {}
        async with self.connect() as db:
            async with db.execute("SELECT key, value FROM config") as cursor:
                async for row in cursor:
                    config[row[0]] = row[1]
        return config

    async def next_run_id(self) -> int:
        async with self.connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute("UPDATE run_counter SET last_run_id = last_run_id + 1")

            async with db.execute("SELECT last_run_id FROM run_counter") as cursor:
                row = await cursor.fetchone()

            await db.commit()
            return row[0]  # pyright: ignore

    async def log_run(self, run_id: int, caption: str):
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
        async with self.connect() as db:
            async with db.execute(
                "SELECT name FROM favorite_platform LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]  # pyright: ignore

    async def set_favorite_platform(self, name: str):
        async with self.connect() as db:
            await db.execute("UPDATE favorite_platform SET name = ?", (name,))
            await db.commit()

    async def clear_logs(self):
        async with self.connect() as db:
            await db.execute("DELETE FROM post_log")
            await db.execute("DELETE FROM run_log")
            await db.execute("UPDATE run_counter SET last_run_id = 0")
            await db.commit()

    async def reset(self):
        self.path.unlink(missing_ok=True)
        await self.initialize()
