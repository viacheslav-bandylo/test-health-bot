"""Tests for typed ScoringConfig model and score validation."""

import pytest
from pydantic import ValidationError

from hea.models.assessment import (
    AssessmentConfig,
    Node,
    NodeType,
    RoutingRule,
    ScoringCategory,
    ScoringConfig,
    ScoringRule,
)


class TestScoringConfig:
    def test_create_scoring_config(self):
        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        assert len(sc.categories) == 1
        assert sc.categories[0].id == "cv_risk"

    def test_empty_categories_allowed(self):
        sc = ScoringConfig(categories=[])
        assert sc.categories == []

    def test_get_category_by_id(self):
        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                ),
                ScoringCategory(
                    id="stress", name="Stress", initial=0, min=0, max=10
                ),
            ]
        )
        cat = sc.get_category("cv_risk")
        assert cat is not None
        assert cat.name == "CV Risk"

    def test_get_missing_category_returns_none(self):
        sc = ScoringConfig(categories=[])
        assert sc.get_category("missing") is None


class TestAssessmentConfigWithScoringConfig:
    def test_scoring_accepts_typed_config(self):
        config = AssessmentConfig(
            id="test",
            version="1.0",
            title="Test",
            description="Test",
            role_prompt="role",
            disclaimer="disc",
            scoring=ScoringConfig(
                categories=[
                    ScoringCategory(
                        id="cv_risk", name="CV", initial=0, min=0, max=20
                    )
                ]
            ),
            nodes=[
                Node(
                    id="start",
                    type=NodeType.QUESTION,
                    instruction="q",
                    scoring_rules=[ScoringRule(match="a", update={})],
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
        assert config.scoring.categories[0].id == "cv_risk"

    def test_scoring_accepts_dict_coercion(self):
        """Dict with categories should be coerced to ScoringConfig."""
        config = AssessmentConfig(
            id="test",
            version="1.0",
            title="Test",
            description="Test",
            role_prompt="role",
            disclaimer="disc",
            scoring={
                "categories": [
                    {"id": "cv_risk", "name": "CV", "initial": 0, "min": 0, "max": 20}
                ]
            },
            nodes=[
                Node(
                    id="start",
                    type=NodeType.QUESTION,
                    instruction="q",
                    scoring_rules=[ScoringRule(match="a", update={})],
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
        assert isinstance(config.scoring, ScoringConfig)
        assert config.scoring.categories[0].id == "cv_risk"


class TestScoreValidation:
    """Tests for validate_score_updates function."""

    def test_valid_score_updates(self):
        from hea.orchestrator.validator import validate_score_updates

        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        errors = validate_score_updates({"cv_risk": 2}, sc, current_scores={})
        assert errors == []

    def test_unknown_score_key_rejected(self):
        from hea.orchestrator.validator import validate_score_updates

        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        errors = validate_score_updates(
            {"unknown_key": 5}, sc, current_scores={}
        )
        assert any("unknown_key" in e for e in errors)

    def test_score_exceeding_max_rejected(self):
        from hea.orchestrator.validator import validate_score_updates

        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        errors = validate_score_updates(
            {"cv_risk": 25}, sc, current_scores={"cv_risk": 0}
        )
        assert any("max" in e.lower() or "exceed" in e.lower() for e in errors)

    def test_score_below_min_rejected(self):
        from hea.orchestrator.validator import validate_score_updates

        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        errors = validate_score_updates(
            {"cv_risk": -5}, sc, current_scores={"cv_risk": 2}
        )
        assert any("min" in e.lower() or "below" in e.lower() for e in errors)

    def test_empty_updates_valid(self):
        from hea.orchestrator.validator import validate_score_updates

        sc = ScoringConfig(
            categories=[
                ScoringCategory(
                    id="cv_risk", name="CV Risk", initial=0, min=0, max=20
                )
            ]
        )
        errors = validate_score_updates({}, sc, current_scores={})
        assert errors == []
