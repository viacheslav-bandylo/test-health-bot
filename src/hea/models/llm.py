"""LLM structured response schema."""

from pydantic import BaseModel


class LLMResponse(BaseModel, frozen=True):
    reasoning: str
    matched_category: str
    score_updates: dict[str, int]
    next_node_id: str
    user_message: str
    needs_clarification: bool
