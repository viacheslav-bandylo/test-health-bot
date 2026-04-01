"""Tests for Telegram HTML formatting utilities."""

from __future__ import annotations

import pytest

from hea.bot.formatting import (
    EMOJI_INFO,
    EMOJI_REPORT,
    escape_html,
    format_disclaimer,
    format_greeting,
    generate_html_report,
)
from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringRule,
)
from hea.models.session import Session, SessionState


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
                {
                    "id": "cv_risk",
                    "name": "Cardiovascular Risk Score",
                    "initial": 0,
                    "min": 0,
                    "max": 20,
                }
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


class TestEscapeHtml:
    def test_escapes_angle_brackets(self):
        assert escape_html("<script>") == "&lt;script&gt;"

    def test_escapes_ampersand(self):
        assert escape_html("A & B") == "A &amp; B"

    def test_preserves_plain_text(self):
        assert escape_html("Hello world") == "Hello world"

    def test_does_not_escape_quotes(self):
        assert escape_html('"hello"') == '"hello"'


class TestFormatDisclaimer:
    def test_wraps_in_italic(self):
        result = format_disclaimer("Some disclaimer")
        assert result == "<i>Some disclaimer</i>"

    def test_strips_whitespace(self):
        result = format_disclaimer("  disclaimer  \n")
        assert result == "<i>disclaimer</i>"

    def test_escapes_html_in_disclaimer(self):
        result = format_disclaimer("Use <b>caution</b>")
        assert result == "<i>Use &lt;b&gt;caution&lt;/b&gt;</i>"


class TestFormatGreeting:
    def test_contains_disclaimer_and_message(self):
        result = format_greeting("Not medical advice.", "How old are you?")
        assert "<i>Not medical advice.</i>" in result
        assert "How old are you?" in result

    def test_disclaimer_is_italic(self):
        result = format_greeting("Disclaimer text", "Question")
        assert "<i>Disclaimer text</i>" in result

    def test_escapes_llm_message(self):
        result = format_greeting("Disclaimer", "Age < 30 or > 50?")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_contains_info_emoji(self):
        result = format_greeting("Disclaimer", "Question")
        assert EMOJI_INFO in result


class TestGenerateHtmlReport:
    def test_contains_bold_title(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 5},
        )
        report = generate_html_report(config, session)
        assert "<b>Cardiovascular Risk Assessment</b>" in report

    def test_contains_report_emoji(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 5},
        )
        report = generate_html_report(config, session)
        assert EMOJI_REPORT in report

    def test_contains_bold_score_value(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 7},
        )
        report = generate_html_report(config, session)
        assert "Cardiovascular Risk Score: <b>7</b>" in report

    def test_contains_italic_disclaimer(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 0},
        )
        report = generate_html_report(config, session)
        assert "<i>Not medical advice.</i>" in report

    def test_contains_results_header(self, config):
        session = Session(
            chat_id=1,
            assessment_id="cardio_risk",
            assessment_version="1.0",
            state=SessionState.COMPLETED,
            scores={"cv_risk": 3},
        )
        report = generate_html_report(config, session)
        assert "<b>Results:</b>" in report
