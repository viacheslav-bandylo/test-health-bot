"""Assessment configuration models — loaded from YAML."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator


class NodeType(StrEnum):
    QUESTION = "question"
    TERMINAL = "terminal"


class ScoringRule(BaseModel, frozen=True):
    match: str
    update: dict[str, int]


class RoutingRule(BaseModel, frozen=True):
    match: str
    next: str


class ScoringCategory(BaseModel, frozen=True):
    id: str
    name: str
    initial: int
    min: int
    max: int

    @model_validator(mode="after")
    def _min_le_max(self) -> ScoringCategory:
        if self.min > self.max:
            msg = f"min ({self.min}) must be <= max ({self.max})"
            raise ValueError(msg)
        return self


class Node(BaseModel, frozen=True):
    id: str
    type: NodeType
    instruction: str
    scoring_rules: list[ScoringRule]
    routing: list[RoutingRule]

    @model_validator(mode="after")
    def _question_needs_routing(self) -> Node:
        if self.type == NodeType.QUESTION and not self.routing:
            msg = "question nodes must have at least one routing rule"
            raise ValueError(msg)
        return self


class ScoringConfig(BaseModel, frozen=True):
    categories: list[ScoringCategory] = []

    def get_category(self, category_id: str) -> ScoringCategory | None:
        for cat in self.categories:
            if cat.id == category_id:
                return cat
        return None


class AssessmentConfig(BaseModel, frozen=True):
    id: str
    version: str
    title: str
    description: str
    role_prompt: str
    disclaimer: str
    scoring: ScoringConfig
    nodes: list[Node]

    @model_validator(mode="after")
    def _validate_graph(self) -> AssessmentConfig:
        # Check unique node ids
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            msg = "duplicate node ids found"
            raise ValueError(msg)

        # Check routing references
        node_id_set = set(node_ids)
        for node in self.nodes:
            for rule in node.routing:
                if rule.next not in node_id_set:
                    msg = f"routing references nonexistent node '{rule.next}'"
                    raise ValueError(msg)

        return self

    def get_node(self, node_id: str) -> Node | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
