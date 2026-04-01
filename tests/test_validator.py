"""Tests for LLM response validator."""

import pytest

from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringCategory,
    ScoringRule,
)
from hea.models.llm import LLMResponse
from hea.orchestrator.validator import ValidationResult, validate_response


@pytest.fixture
def config():
    return AssessmentConfig(
        id="test",
        version="1.0",
        title="Test",
        description="Test",
        role_prompt="role",
        disclaimer="disc",
        scoring={
            "categories": [
                {"id": "cv_risk", "name": "CV Risk", "initial": 0, "min": 0, "max": 20}
            ]
        },
        nodes=[
            Node(
                id="start",
                type=NodeType.QUESTION,
                instruction="Ask age",
                scoring_rules=[
                    ScoringRule(match="young", update={"cv_risk": 0}),
                    ScoringRule(match="old", update={"cv_risk": 4}),
                ],
                routing=[
                    RoutingRule(match="*", next="end"),
                ],
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


class TestValidateResponse:
    def test_valid_response(self, config):
        resp = LLMResponse(
            reasoning="test",
            matched_category="young",
            score_updates={"cv_risk": 0},
            next_node_id="end",
            user_message="Hello!",
            needs_clarification=False,
        )
        result = validate_response(resp, config, "start")
        assert result.is_valid
        assert result.errors == []

    def test_clarification_is_always_valid(self, config):
        resp = LLMResponse(
            reasoning="unclear",
            matched_category="",
            score_updates={},
            next_node_id="start",
            user_message="Can you clarify?",
            needs_clarification=True,
        )
        result = validate_response(resp, config, "start")
        assert result.is_valid

    def test_invalid_next_node(self, config):
        resp = LLMResponse(
            reasoning="test",
            matched_category="young",
            score_updates={"cv_risk": 0},
            next_node_id="nonexistent",
            user_message="Hello!",
            needs_clarification=False,
        )
        result = validate_response(resp, config, "start")
        assert not result.is_valid
        assert any("node" in e.lower() for e in result.errors)

    def test_invalid_category(self, config):
        resp = LLMResponse(
            reasoning="test",
            matched_category="invented_category",
            score_updates={"cv_risk": 0},
            next_node_id="end",
            user_message="Hello!",
            needs_clarification=False,
        )
        result = validate_response(resp, config, "start")
        assert not result.is_valid
        assert any("category" in e.lower() for e in result.errors)

    def test_unreachable_next_node(self, config):
        """next_node_id exists but is not in routing rules for current node."""
        # Add a third node not reachable from start
        from hea.models.assessment import AssessmentConfig, Node

        config_with_extra = AssessmentConfig(
            id="test",
            version="1.0",
            title="Test",
            description="Test",
            role_prompt="role",
            disclaimer="disc",
            scoring={"categories": []},
            nodes=[
                Node(
                    id="start",
                    type=NodeType.QUESTION,
                    instruction="Ask",
                    scoring_rules=[ScoringRule(match="a", update={})],
                    routing=[RoutingRule(match="*", next="end")],
                ),
                Node(id="end", type=NodeType.TERMINAL, instruction="Done",
                     scoring_rules=[], routing=[]),
                Node(
                    id="unreachable",
                    type=NodeType.QUESTION,
                    instruction="Ask",
                    scoring_rules=[],
                    routing=[RoutingRule(match="*", next="end")],
                ),
            ],
        )
        resp = LLMResponse(
            reasoning="test",
            matched_category="a",
            score_updates={},
            next_node_id="unreachable",
            user_message="Hello!",
            needs_clarification=False,
        )
        result = validate_response(resp, config_with_extra, "start")
        assert not result.is_valid
        assert any("routing" in e.lower() or "reachable" in e.lower() for e in result.errors)
