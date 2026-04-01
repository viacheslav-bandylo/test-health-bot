"""Tests for assessment path in Settings."""

from pathlib import Path

from hea.settings import Settings


class TestSettingsAssessmentPath:
    def test_default_assessment_path(self):
        settings = Settings(
            telegram_bot_token="fake",
            openrouter_api_key="fake",
        )
        assert settings.assessment_path == Path("assessments/cardio_risk_v1.yaml")

    def test_custom_assessment_path(self):
        settings = Settings(
            telegram_bot_token="fake",
            openrouter_api_key="fake",
            assessment_path=Path("/custom/path.yaml"),
        )
        assert settings.assessment_path == Path("/custom/path.yaml")
