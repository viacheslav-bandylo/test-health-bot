"""Integration tests for the orchestrator engine (with mock LLM)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from hea.assessment.loader import load_assessment
from hea.models.llm import LLMResponse
from hea.models.session import Session, SessionState
from hea.orchestrator.engine import Orchestrator

ASSESSMENTS_DIR = Path(__file__).parent.parent / "assessments"


@pytest.fixture
def config():
    return load_assessment(ASSESSMENTS_DIR / "cardio_risk_v1.yaml")


@pytest.fixture
def session():
    return Session(
        chat_id=1,
        assessment_id="cardio_risk",
        assessment_version="1.0",
    )


def make_llm_response(
    *,
    category: str,
    scores: dict[str, int],
    next_node: str,
    message: str = "OK",
    clarify: bool = False,
) -> LLMResponse:
    return LLMResponse(
        reasoning="test",
        matched_category=category,
        score_updates=scores,
        next_node_id=next_node,
        user_message=message,
        needs_clarification=clarify,
    )


class TestOrchestrator:
    async def test_full_flow_three_questions_to_report(self, config, session):
        """Full happy path: start -> smoking -> exercise -> result."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            # start: age 30-50
            make_llm_response(
                category="30_to_50",
                scores={"cv_risk": 2},
                next_node="smoking",
                message="Got it, you're between 30 and 50.",
            ),
            # smoking: never
            make_llm_response(
                category="never",
                scores={"cv_risk": 0},
                next_node="exercise",
                message="Great, you don't smoke!",
            ),
            # exercise: sedentary
            make_llm_response(
                category="sedentary",
                scores={"cv_risk": 3},
                next_node="result",
                message="Here are your results.",
            ),
        ]

        orch = Orchestrator(config=config, llm_client=mock_llm, max_clarifications=3)

        # Question 1
        result_session, msg = await orch.process_message(session, "I'm 35")
        assert result_session.current_node_id == "smoking"
        assert result_session.scores == {"cv_risk": 2}

        # Question 2
        result_session, msg = await orch.process_message(result_session, "Never smoked")
        assert result_session.current_node_id == "exercise"
        assert result_session.scores == {"cv_risk": 2}

        # Question 3
        result_session, msg = await orch.process_message(result_session, "I don't exercise")
        assert result_session.current_node_id == "result"
        assert result_session.scores == {"cv_risk": 5}
        assert result_session.state == SessionState.COMPLETED

    async def test_clarification_flow(self, config, session):
        """When LLM says needs_clarification, stay on same node."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            make_llm_response(
                category="",
                scores={},
                next_node="start",
                message="Could you clarify your age?",
                clarify=True,
            ),
            make_llm_response(
                category="under_30",
                scores={"cv_risk": 0},
                next_node="smoking",
                message="Got it, you're under 30!",
            ),
        ]

        orch = Orchestrator(config=config, llm_client=mock_llm, max_clarifications=3)

        # First attempt — unclear
        result_session, msg = await orch.process_message(session, "hmm not sure")
        assert result_session.current_node_id == "start"
        assert result_session.clarification_count == 1
        assert "clarify" in msg.lower()

        # Second attempt — clear
        result_session, msg = await orch.process_message(result_session, "I'm 25")
        assert result_session.current_node_id == "smoking"

    async def test_max_clarifications_fallback(self, config, session):
        """After max clarifications, use fallback routing."""
        mock_llm = AsyncMock()
        # Always return unclear
        mock_llm.complete.return_value = make_llm_response(
            category="",
            scores={},
            next_node="start",
            message="I still don't understand",
            clarify=True,
        )

        orch = Orchestrator(config=config, llm_client=mock_llm, max_clarifications=2)

        # Clarification 1
        s, _ = await orch.process_message(session, "???")
        assert s.clarification_count == 1

        # Clarification 2
        s, _ = await orch.process_message(s, "??")
        assert s.clarification_count == 2

        # Clarification 3 — should fallback
        s, msg = await orch.process_message(s, "?")
        assert s.current_node_id == "smoking"  # fallback to first routing rule
        assert s.clarification_count == 0

    async def test_invalid_llm_response_retries(self, config, session):
        """When LLM gives invalid response, retry once then fallback."""
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = [
            # First: invalid category
            make_llm_response(
                category="invented",
                scores={"cv_risk": 99},
                next_node="nonexistent",
                message="Wrong answer",
            ),
            # Retry: still invalid
            make_llm_response(
                category="invented2",
                scores={"cv_risk": 99},
                next_node="nonexistent",
                message="Still wrong",
            ),
        ]

        orch = Orchestrator(config=config, llm_client=mock_llm, max_clarifications=3)

        s, msg = await orch.process_message(session, "I'm 35")
        # Should have fallen back to first routing rule
        assert s.current_node_id == "smoking"
        # Fallback uses first scoring rule's update
        assert mock_llm.complete.call_count == 2

    async def test_start_generates_first_question(self, config):
        """Starting a new session should generate the first question."""
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = make_llm_response(
            category="",
            scores={},
            next_node="start",
            message="Hello! How old are you?",
            clarify=False,
        )

        orch = Orchestrator(config=config, llm_client=mock_llm, max_clarifications=3)
        session, msg = await orch.start_session(chat_id=42)
        assert session.chat_id == 42
        assert session.current_node_id == "start"
        assert msg == "Hello! How old are you?"
