"""Tests for SessionRepository context manager and error handling."""

import pytest

from hea.storage.repository import SessionRepository


class TestSessionRepositoryContextManager:
    async def test_aenter_initializes_and_returns_self(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        repo = SessionRepository(db_path)
        async with repo as r:
            assert r is repo
            assert repo._db is not None

    async def test_aexit_closes_connection(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        repo = SessionRepository(db_path)
        async with repo:
            pass
        assert repo._db is None


class TestSessionRepositoryNotInitialized:
    async def test_save_without_init_raises_runtime_error(self, tmp_path):
        from hea.models.session import Session

        repo = SessionRepository(str(tmp_path / "test.db"))
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
        )
        with pytest.raises(RuntimeError, match="not initialized"):
            await repo.save(session)

    async def test_get_without_init_raises_runtime_error(self, tmp_path):
        repo = SessionRepository(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await repo.get_by_chat_id(1)

    async def test_delete_without_init_raises_runtime_error(self, tmp_path):
        repo = SessionRepository(str(tmp_path / "test.db"))
        with pytest.raises(RuntimeError, match="not initialized"):
            await repo.delete(1)
