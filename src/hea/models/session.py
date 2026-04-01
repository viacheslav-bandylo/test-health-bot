"""Session state models — immutable, new object on each transition."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SessionState(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class HistoryEntry(BaseModel, frozen=True):
    node_id: str
    user_answer: str
    assistant_message: str


class Session(BaseModel, frozen=True):
    chat_id: int
    assessment_id: str
    assessment_version: str
    state: SessionState = SessionState.IN_PROGRESS
    current_node_id: str = "start"
    scores: dict[str, int] = Field(default_factory=dict)
    history: list[HistoryEntry] = Field(default_factory=list)
    clarification_count: int = 0

    def advance(
        self,
        *,
        next_node_id: str,
        score_updates: dict[str, int],
        user_answer: str,
        assistant_message: str,
    ) -> Session:
        new_scores = dict(self.scores)
        for key, delta in score_updates.items():
            new_scores[key] = new_scores.get(key, 0) + delta

        entry = HistoryEntry(
            node_id=self.current_node_id,
            user_answer=user_answer,
            assistant_message=assistant_message,
        )

        return self.model_copy(
            update={
                "current_node_id": next_node_id,
                "scores": new_scores,
                "history": [*self.history, entry],
                "clarification_count": 0,
            }
        )

    def increment_clarification(self) -> Session:
        return self.model_copy(
            update={"clarification_count": self.clarification_count + 1}
        )

    def complete(self) -> Session:
        return self.model_copy(update={"state": SessionState.COMPLETED})
