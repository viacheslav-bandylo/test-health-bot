"""Application settings from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_model: str = "google/gemini-2.5-flash-preview"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    database_path: str = "data/sessions.db"
    llm_timeout_seconds: int = 15
    max_clarifications_per_node: int = 3
    assessment_path: Path = Path("assessments/cardio_risk_v1.yaml")
    max_message_length: int = 500
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
