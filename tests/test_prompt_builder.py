"""Tests for LLM prompt builder."""

import json

import pytest

from hea.llm.prompt_builder import build_system_prompt, build_user_prompt
from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringRule,
)
from hea.models.session import HistoryEntry, Session


@pytest.fixture
def config():
    return AssessmentConfig(
        id="cardio_risk",
        version="1.0",
        title="Cardio Risk",
        description="Quick screening",
        role_prompt="You are a friendly health assistant.",
        disclaimer="Not medical advice.",
        scoring={
            "categories": [
                {"id": "cv_risk", "name": "CV Risk", "initial": 0, "min": 0, "max": 20}
            ]
        },
        nodes=[
            Node(
                id="start",
                type=NodeType.QUESTION,
                instruction="Ask the user about their age.",
                scoring_rules=[
                    ScoringRule(match="under_30", update={"cv_risk": 0}),
                    ScoringRule(match="over_50", update={"cv_risk": 4}),
                ],
                routing=[RoutingRule(match="*", next="result")],
            ),
            Node(
                id="result",
                type=NodeType.TERMINAL,
                instruction="Show results",
                scoring_rules=[],
                routing=[],
            ),
        ],
    )


@pytest.fixture
def session():
    return Session(
        chat_id=1,
        assessment_id="cardio_risk",
        assessment_version="1.0",
        scores={"cv_risk": 2},
        history=[
            HistoryEntry(
                node_id="intro",
                user_answer="Hello",
                assistant_message="Welcome!",
            )
        ],
    )


class TestBuildSystemPrompt:
    def test_contains_role_prompt(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "friendly health assistant" in prompt

    def test_contains_current_node_instruction(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "Ask the user about their age" in prompt

    def test_contains_scoring_categories(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "under_30" in prompt
        assert "over_50" in prompt

    def test_contains_routing_rules(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "result" in prompt

    def test_contains_current_scores(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "cv_risk" in prompt
        assert "2" in prompt

    def test_contains_response_format(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "matched_category" in prompt
        assert "needs_clarification" in prompt

    def test_contains_history_summary(self, config, session):
        prompt = build_system_prompt(config, session)
        assert "Hello" in prompt


class TestBuildUserPrompt:
    def test_wraps_user_message(self):
        prompt = build_user_prompt("I'm 35 years old")
        assert "I'm 35 years old" in prompt
