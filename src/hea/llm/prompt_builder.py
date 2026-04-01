"""Build prompts for the LLM from current assessment state."""

from __future__ import annotations

from hea.models.assessment import AssessmentConfig
from hea.models.session import Session


def build_system_prompt(config: AssessmentConfig, session: Session) -> str:
    """Build the system prompt for the current node."""
    node = config.get_node(session.current_node_id)
    if node is None:
        raise ValueError(f"Node '{session.current_node_id}' not found in config")

    # Scoring categories for current node
    categories_text = "\n".join(
        f"  - {rule.match}: score updates {rule.update}"
        for rule in node.scoring_rules
    )

    # Routing rules
    routing_text = "\n".join(
        f"  - match: {rule.match} -> next: {rule.next}"
        for rule in node.routing
    )

    # Current scores
    scores_text = ", ".join(
        f"{k}: {v}" for k, v in session.scores.items()
    ) or "none yet"

    # History summary (last 3)
    history_entries = session.history[-3:]
    history_text = "\n".join(
        f"  - [Node: {e.node_id}] User: {e.user_answer}"
        for e in history_entries
    ) or "  (no history)"

    return f"""{config.role_prompt.strip()}

## Current Node: {node.id}
{node.instruction.strip()}

## Answer Categories (classify user's response into one):
{categories_text}

## Routing Rules:
{routing_text}

## Current Scores: {scores_text}

## Recent History:
{history_text}

## Formatting Policy:
In the "user_message" field, when you present answer choices you MUST:
1. Use human-friendly labels (e.g. "Under 30" not "under_30")
2. Put each option on its own line using a literal newline character in the JSON string
3. Prefix each option with "• "
Example user_message: "Which age group do you fall into?\n\n• Under 30\n• 30 to 50\n• Over 50"
NEVER list options inline separated by commas or dots.

## Language Policy:
You MUST always respond in English only. If the user writes in a language other than English, set "needs_clarification" to true and politely ask them to rephrase in English. Do NOT attempt to classify or score non-English messages.

## Response Format (strict JSON):
You MUST respond with a JSON object containing exactly these fields:
- "reasoning": string — your chain-of-thought analysis (hidden from user)
- "matched_category": string — one of the categories above (empty if needs_clarification)
- "score_updates": object — score changes based on matched category's rules
- "next_node_id": string — valid node from routing rules
- "user_message": string — your message to show the user (always in English)
- "needs_clarification": boolean — true if the user's answer is unclear or not in English
"""


def build_user_prompt(user_message: str) -> str:
    """Wrap the user's message for the LLM."""
    return f"User's message: {user_message}"
