"""Tests for orchestrator LLM error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from hea.llm.exceptions import LLMAPIError, LLMTimeoutError
from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringConfig,
    ScoringCategory,
    ScoringRule,
)
from hea.models.session import Session
from hea.orchestrator.engine import Orchestrator


@pytest.fixture
def config():
    return AssessmentConfig(
        id="test",
        version="1.0",
        title="Test",
        description="Test",
        role_prompt="role",
        disclaimer="disc",
        scoring=ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        ),
        nodes=[
            Node(
                id="start",
                type=NodeType.QUESTION,
                instruction="Ask age",
                scoring_rules=[ScoringRule(match="young", update={"cv_risk": 0})],
                routing=[RoutingRule(match="*", next="end")],
            ),
            Node(
                id="end",
                type=NodeType.TERMINAL,
                instruction="Done",
                scoring_rules=[],
                routing=[],
            ),
        ],
    )


@pytest.fixture
def session():
    return Session(
        chat_id=1,
        assessment_id="test",
        assessment_version="1.0",
    )


class TestOrchestratorLLMErrors:
    async def test_llm_timeout_returns_error_message(self, config, session):
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = LLMTimeoutError("timed out")

        orch = Orchestrator(config=config, llm_client=mock_llm)
        new_session, msg = await orch.process_message(session, "hello")

        # Should return same session (no state change) + error message
        assert new_session.current_node_id == session.current_node_id
        assert "try again" in msg.lower() or "error" in msg.lower()

    async def test_llm_api_error_returns_error_message(self, config, session):
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = LLMAPIError("500 error")

        orch = Orchestrator(config=config, llm_client=mock_llm)
        new_session, msg = await orch.process_message(session, "hello")

        assert new_session.current_node_id == session.current_node_id
        assert "try again" in msg.lower() or "error" in msg.lower()

    async def test_start_session_llm_error_propagates(self, config):
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = LLMTimeoutError("timed out")

        orch = Orchestrator(config=config, llm_client=mock_llm)
        with pytest.raises(LLMTimeoutError):
            await orch.start_session(chat_id=42)
