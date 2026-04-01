"""Async SQLite session repository."""

from __future__ import annotations

import aiosqlite

from hea.models.session import Session
from hea.storage.migrations import run_migrations


class SessionRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def __aenter__(self) -> SessionRepository:
        await self.initialize()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await run_migrations(self._db)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError(
                "Repository not initialized. Call initialize() first."
            )
        return self._db

    async def save(self, session: Session) -> None:
        db = self._ensure_db()
        await db.execute(
            "INSERT OR REPLACE INTO sessions (chat_id, data) VALUES (?, ?)",
            (session.chat_id, session.model_dump_json()),
        )
        await db.commit()

    async def get_by_chat_id(self, chat_id: int) -> Session | None:
        db = self._ensure_db()
        cursor = await db.execute(
            "SELECT data FROM sessions WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return Session.model_validate_json(row[0])

    async def delete(self, chat_id: int) -> None:
        db = self._ensure_db()
        await db.execute(
            "DELETE FROM sessions WHERE chat_id = ?",
            (chat_id,),
        )
        await db.commit()
