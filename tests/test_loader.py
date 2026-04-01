"""Tests for YAML assessment loader."""

from pathlib import Path

import pytest

from hea.assessment.loader import load_assessment
from hea.models.assessment import AssessmentConfig, NodeType

ASSESSMENTS_DIR = Path(__file__).parent.parent / "assessments"


class TestLoadAssessment:
    def test_load_cardio_risk(self):
        config = load_assessment(ASSESSMENTS_DIR / "cardio_risk_v1.yaml")
        assert isinstance(config, AssessmentConfig)
        assert config.id == "cardio_risk"
        assert config.version == "1.0"

    def test_nodes_loaded(self):
        config = load_assessment(ASSESSMENTS_DIR / "cardio_risk_v1.yaml")
        assert len(config.nodes) == 4
        assert config.nodes[0].id == "start"
        assert config.nodes[-1].type == NodeType.TERMINAL

    def test_scoring_categories_loaded(self):
        config = load_assessment(ASSESSMENTS_DIR / "cardio_risk_v1.yaml")
        cats = config.scoring.categories
        assert len(cats) == 1
        assert cats[0].id == "cv_risk"

    def test_scoring_rules_loaded(self):
        config = load_assessment(ASSESSMENTS_DIR / "cardio_risk_v1.yaml")
        start = config.get_node("start")
        assert len(start.scoring_rules) == 3
        assert start.scoring_rules[0].match == "under_30"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_assessment(Path("/nonexistent/file.yaml"))

    def test_invalid_yaml_raises(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("id: test\n  broken: yaml: [")
        with pytest.raises(Exception):
            load_assessment(bad_file)
