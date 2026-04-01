"""Tests for Pydantic data models — assessment, session, llm."""

import pytest
from pydantic import ValidationError

from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringCategory,
    ScoringRule,
)
from hea.models.session import Session, SessionState
from hea.models.llm import LLMResponse


# ── AssessmentConfig models ──────────────────────────────────────────


class TestScoringRule:
    def test_create(self):
        rule = ScoringRule(match="under_30", update={"cv_risk": 0})
        assert rule.match == "under_30"
        assert rule.update == {"cv_risk": 0}

    def test_empty_update_allowed(self):
        rule = ScoringRule(match="skip", update={})
        assert rule.update == {}


class TestRoutingRule:
    def test_wildcard(self):
        rule = RoutingRule(match="*", next="smoking")
        assert rule.match == "*"
        assert rule.next == "smoking"

    def test_conditional(self):
        rule = RoutingRule(match="high_risk", next="urgent")
        assert rule.match == "high_risk"


class TestScoringCategory:
    def test_create(self):
        cat = ScoringCategory(id="cv_risk", name="CV Risk", initial=0, min=0, max=20)
        assert cat.id == "cv_risk"
        assert cat.initial == 0
        assert cat.min == 0
        assert cat.max == 20

    def test_min_greater_than_max_rejected(self):
        with pytest.raises(ValidationError):
            ScoringCategory(id="bad", name="Bad", initial=0, min=10, max=5)


class TestNode:
    def test_question_node(self):
        node = Node(
            id="start",
            type=NodeType.QUESTION,
            instruction="Ask about age",
            scoring_rules=[ScoringRule(match="young", update={"cv_risk": 0})],
            routing=[RoutingRule(match="*", next="next_q")],
        )
        assert node.id == "start"
        assert node.type == NodeType.QUESTION
        assert len(node.scoring_rules) == 1
        assert len(node.routing) == 1

    def test_terminal_node_no_routing_required(self):
        node = Node(
            id="result",
            type=NodeType.TERMINAL,
            instruction="Show results",
            scoring_rules=[],
            routing=[],
        )
        assert node.type == NodeType.TERMINAL
        assert node.routing == []

    def test_question_node_requires_routing(self):
        with pytest.raises(ValidationError):
            Node(
                id="broken",
                type=NodeType.QUESTION,
                instruction="Ask something",
                scoring_rules=[],
                routing=[],
            )


class TestAssessmentConfig:
    def test_full_config(self):
        config = AssessmentConfig(
            id="cardio_risk",
            version="1.0",
            title="Cardio Risk",
            description="Quick screening",
            role_prompt="You are a friendly assistant.",
            disclaimer="Not medical advice.",
            scoring={"categories": [
                {"id": "cv_risk", "name": "CV Risk", "initial": 0, "min": 0, "max": 20}
            ]},
            nodes=[
                Node(
                    id="start",
                    type=NodeType.QUESTION,
                    instruction="Ask age",
                    scoring_rules=[ScoringRule(match="young", update={"cv_risk": 0})],
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
        assert config.id == "cardio_risk"
        assert len(config.nodes) == 2
        assert len(config.scoring.categories) == 1

    def test_node_ids_must_be_unique(self):
        with pytest.raises(ValidationError, match="duplicate"):
            AssessmentConfig(
                id="bad",
                version="1.0",
                title="Bad",
                description="Bad config",
                role_prompt="role",
                disclaimer="disc",
                scoring={"categories": []},
                nodes=[
                    Node(
                        id="same_id",
                        type=NodeType.QUESTION,
                        instruction="q1",
                        scoring_rules=[],
                        routing=[RoutingRule(match="*", next="same_id")],
                    ),
                    Node(
                        id="same_id",
                        type=NodeType.TERMINAL,
                        instruction="q2",
                        scoring_rules=[],
                        routing=[],
                    ),
                ],
            )

    def test_routing_references_valid_nodes(self):
        with pytest.raises(ValidationError, match="nonexistent"):
            AssessmentConfig(
                id="bad",
                version="1.0",
                title="Bad",
                description="Bad config",
                role_prompt="role",
                disclaimer="disc",
                scoring={"categories": []},
                nodes=[
                    Node(
                        id="start",
                        type=NodeType.QUESTION,
                        instruction="q1",
                        scoring_rules=[],
                        routing=[RoutingRule(match="*", next="nonexistent_node")],
                    ),
                ],
            )

    def test_get_node_by_id(self):
        config = AssessmentConfig(
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
                    instruction="q",
                    scoring_rules=[],
                    routing=[RoutingRule(match="*", next="end")],
                ),
                Node(
                    id="end",
                    type=NodeType.TERMINAL,
                    instruction="done",
                    scoring_rules=[],
                    routing=[],
                ),
            ],
        )
        assert config.get_node("start").id == "start"
        assert config.get_node("end").id == "end"
        assert config.get_node("missing") is None


# ── Session models ───────────────────────────────────────────────────


class TestSession:
    def test_create_new_session(self):
        session = Session(
            chat_id=12345,
            assessment_id="cardio_risk",
            assessment_version="1.0",
        )
        assert session.chat_id == 12345
        assert session.state == SessionState.IN_PROGRESS
        assert session.current_node_id == "start"
        assert session.scores == {}
        assert session.history == []
        assert session.clarification_count == 0

    def test_session_is_frozen(self):
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
        )
        with pytest.raises(ValidationError):
            session.current_node_id = "other"

    def test_session_advance(self):
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
        )
        new_session = session.advance(
            next_node_id="smoking",
            score_updates={"cv_risk": 2},
            user_answer="I'm 35",
            assistant_message="Got it!",
        )
        assert new_session.current_node_id == "smoking"
        assert new_session.scores == {"cv_risk": 2}
        assert len(new_session.history) == 1
        assert new_session.clarification_count == 0
        # original unchanged
        assert session.current_node_id == "start"

    def test_session_advance_accumulates_scores(self):
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
            scores={"cv_risk": 2},
        )
        new_session = session.advance(
            next_node_id="exercise",
            score_updates={"cv_risk": 4},
            user_answer="I smoke",
            assistant_message="Noted.",
        )
        assert new_session.scores == {"cv_risk": 6}

    def test_session_increment_clarification(self):
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
        )
        new_session = session.increment_clarification()
        assert new_session.clarification_count == 1
        assert session.clarification_count == 0

    def test_session_complete(self):
        session = Session(
            chat_id=1,
            assessment_id="test",
            assessment_version="1.0",
        )
        completed = session.complete()
        assert completed.state == SessionState.COMPLETED


class TestSessionState:
    def test_states_exist(self):
        assert SessionState.IN_PROGRESS.value == "in_progress"
        assert SessionState.COMPLETED.value == "completed"


# ── LLM Response model ──────────────────────────────────────────────


class TestLLMResponse:
    def test_valid_response(self):
        resp = LLMResponse(
            reasoning="User said they are 35 years old",
            matched_category="30_to_50",
            score_updates={"cv_risk": 2},
            next_node_id="smoking",
            user_message="Thanks! Now about smoking...",
            needs_clarification=False,
        )
        assert resp.matched_category == "30_to_50"
        assert resp.needs_clarification is False

    def test_clarification_response(self):
        resp = LLMResponse(
            reasoning="User's answer is ambiguous",
            matched_category="",
            score_updates={},
            next_node_id="start",
            user_message="Could you clarify?",
            needs_clarification=True,
        )
        assert resp.needs_clarification is True

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            LLMResponse(
                reasoning="test",
                # missing matched_category and others
            )
