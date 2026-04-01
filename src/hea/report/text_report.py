"""Generate text-based assessment reports."""

from __future__ import annotations

from hea.models.assessment import AssessmentConfig
from hea.models.session import Session


def generate_report(config: AssessmentConfig, session: Session) -> str:
    """Generate a text report from a completed session."""
    lines: list[str] = []

    lines.append(f"--- {config.title} ---")
    lines.append("")

    # Scores
    scoring_categories = {
        cat.id: cat.name
        for cat in config.scoring.categories
    }

    lines.append("Results:")
    for score_id, value in session.scores.items():
        name = scoring_categories.get(score_id, score_id)
        lines.append(f"  {name}: {value}")

    lines.append("")

    # Disclaimer
    lines.append(config.disclaimer.strip())

    return "\n".join(lines)
