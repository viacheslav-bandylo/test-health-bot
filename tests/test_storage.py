"""Tests for SQLite session repository."""

import pytest

from hea.models.session import Session, SessionState
from hea.storage.repository import SessionRepository


@pytest.fixture
async def repo(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository = SessionRepository(db_path)
    await repository.initialize()
    yield repository
    await repository.close()


class TestSessionRepository:
    async def test_save_and_load(self, repo):
        session = Session(
            chat_id=123,
            assessment_id="cardio_risk",
            assessment_version="1.0",
        )
        await repo.save(session)
        loaded = await repo.get_by_chat_id(123)
        assert loaded is not None
        assert loaded.chat_id == 123
        assert loaded.assessment_id == "cardio_risk"
        assert loaded.state == SessionState.IN_PROGRESS

    async def test_get_nonexistent_returns_none(self, repo):
        loaded = await repo.get_by_chat_id(999)
        assert loaded is None

    async def test_update_session(self, repo):
        session = Session(
            chat_id=100,
            assessment_id="test",
            assessment_version="1.0",
        )
        await repo.save(session)

        updated = session.advance(
            next_node_id="smoking",
            score_updates={"cv_risk": 2},
            user_answer="I'm 40",
            assistant_message="Thanks!",
        )
        await repo.save(updated)

        loaded = await repo.get_by_chat_id(100)
        assert loaded.current_node_id == "smoking"
        assert loaded.scores == {"cv_risk": 2}
        assert len(loaded.history) == 1

    async def test_delete_session(self, repo):
        session = Session(
            chat_id=200,
            assessment_id="test",
            assessment_version="1.0",
        )
        await repo.save(session)
        await repo.delete(200)
        assert await repo.get_by_chat_id(200) is None
