"""Telegram HTML formatting utilities for bot messages."""

from __future__ import annotations

from hea.models.assessment import AssessmentConfig
from hea.models.session import Session

EMOJI_INFO = "\u2139\ufe0f"
EMOJI_REPORT = "\U0001f4ca"


def escape_html(text: str) -> str:
    """Escape characters that break Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_disclaimer(disclaimer: str) -> str:
    """Format disclaimer as italic HTML text."""
    return f"<i>{escape_html(disclaimer.strip())}</i>"


def format_greeting(disclaimer: str, llm_message: str) -> str:
    """Build a formatted greeting with emoji, disclaimer, and LLM question."""
    return f"{EMOJI_INFO} {format_disclaimer(disclaimer)}\n\n{escape_html(llm_message)}"


def generate_html_report(config: AssessmentConfig, session: Session) -> str:
    """Generate an HTML-formatted assessment report."""
    lines: list[str] = []
    lines.append(f"{EMOJI_REPORT} <b>{escape_html(config.title)}</b>")
    lines.append("")
    lines.append("<b>Results:</b>")

    for cat in config.scoring.categories:
        score = session.scores.get(cat.id, cat.initial)
        lines.append(f"{escape_html(cat.name)}: <b>{score}</b>")

    lines.append("")
    lines.append(format_disclaimer(config.disclaimer))

    return "\n".join(lines)
