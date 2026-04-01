"""Tests for text report generator."""

import pytest

from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringRule,
)
from hea.models.session import HistoryEntry, Session, SessionState
from hea.report.text_report import generate_report


@pytest.fixture
def config():
    return AssessmentConfig(
        id="cardio_risk",
        version="1.0",
        title="Cardiovascular Risk Assessment",
        description="Quick screening",
        role_prompt="role",
        disclaimer="Not medical advice.",
        scoring={
            "categories": [
                {"id": "cv_risk", "name": "Cardiovascular Risk Score",
                 "initial": 0, "min": 0, "max": 20}
            ]
        },
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


class TestGenerateReport:
    def test_report_contains_title(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 5},
            history=[],
        )
        report = generate_report(config, session)
        assert "Cardiovascular Risk Assessment" in report

    def test_report_contains_scores(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 5},
            history=[],
        )
        report = generate_report(config, session)
        assert "cv_risk" in report or "Cardiovascular Risk Score" in report
        assert "5" in report

    def test_report_contains_disclaimer(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 0},
            history=[],
        )
        report = generate_report(config, session)
        assert "Not medical advice" in report

    def test_report_with_history(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 3},
            history=[
                HistoryEntry(node_id="start", user_answer="I'm 25",
                             assistant_message="Got it!"),
            ],
        )
        report = generate_report(config, session)
        assert len(report) > 0
