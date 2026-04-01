"""Validate LLM responses against assessment config rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from hea.models.assessment import AssessmentConfig, ScoringConfig
from hea.models.llm import LLMResponse


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def validate_score_updates(
    score_updates: dict[str, int],
    scoring: ScoringConfig,
    current_scores: dict[str, int],
) -> list[str]:
    """Validate score updates against scoring config bounds."""
    errors: list[str] = []
    valid_ids = {cat.id for cat in scoring.categories}

    for key, delta in score_updates.items():
        if key not in valid_ids:
            errors.append(f"Unknown score category '{key}'")
            continue

        cat = scoring.get_category(key)
        if cat is None:
            continue

        current = current_scores.get(key, cat.initial)
        new_value = current + delta
        if new_value > cat.max:
            errors.append(
                f"Score '{key}' would exceed max ({new_value} > {cat.max})"
            )
        if new_value < cat.min:
            errors.append(
                f"Score '{key}' would go below min ({new_value} < {cat.min})"
            )

    return errors


def validate_response(
    response: LLMResponse,
    config: AssessmentConfig,
    current_node_id: str,
) -> ValidationResult:
    """Validate an LLM response against the assessment config.

    Clarification responses are always considered valid.
    """
    if response.needs_clarification:
        return ValidationResult(is_valid=True)

    errors: list[str] = []
    node = config.get_node(current_node_id)
    if node is None:
        return ValidationResult(
            is_valid=False,
            errors=[f"Current node '{current_node_id}' not found in config"],
        )

    # 1. Check next_node_id exists in graph
    if config.get_node(response.next_node_id) is None:
        errors.append(f"Next node '{response.next_node_id}' does not exist in graph")

    # 2. Check next_node_id is reachable from current node via routing
    reachable_nodes = {rule.next for rule in node.routing}
    if response.next_node_id not in reachable_nodes:
        errors.append(
            f"Next node '{response.next_node_id}' is not reachable from "
            f"'{current_node_id}' via routing rules"
        )

    # 3. Check matched_category is valid for current node
    valid_categories = {rule.match for rule in node.scoring_rules}
    if response.matched_category not in valid_categories:
        errors.append(
            f"Category '{response.matched_category}' is not valid for node "
            f"'{current_node_id}'. Valid: {valid_categories}"
        )

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)
