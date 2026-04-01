"""SQLite schema creation."""

import aiosqlite

CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    chat_id INTEGER PRIMARY KEY,
    data TEXT NOT NULL
);
"""


async def run_migrations(db: aiosqlite.Connection) -> None:
    await db.execute(CREATE_SESSIONS_TABLE)
    await db.commit()
