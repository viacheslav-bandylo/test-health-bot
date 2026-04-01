"""YAML assessment config loader."""

from pathlib import Path

import yaml

from hea.models.assessment import AssessmentConfig


def load_assessment(path: Path) -> AssessmentConfig:
    """Load and validate an assessment config from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Assessment file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AssessmentConfig.model_validate(raw)
