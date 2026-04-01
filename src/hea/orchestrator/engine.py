"""Orchestrator — the core state machine that drives assessments."""

from __future__ import annotations

import logging
from typing import Protocol

from hea.llm.exceptions import LLMError
from hea.models.assessment import AssessmentConfig, NodeType
from hea.models.llm import LLMResponse
from hea.models.session import Session
from hea.llm.prompt_builder import build_system_prompt, build_user_prompt
from hea.orchestrator.validator import validate_response, validate_score_updates

logger = logging.getLogger(__name__)

_LLM_ERROR_MSG = (
    "Sorry, something went wrong. Please try again in a moment."
)


class LLMClientProtocol(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse: ...


class Orchestrator:
    def __init__(
        self,
        *,
        config: AssessmentConfig,
        llm_client: LLMClientProtocol,
        max_clarifications: int = 3,
    ) -> None:
        self._config = config
        self._llm = llm_client
        self._max_clarifications = max_clarifications

    async def start_session(self, chat_id: int) -> tuple[Session, str]:
        """Create a new session and generate the first question."""
        session = Session(
            chat_id=chat_id,
            assessment_id=self._config.id,
            assessment_version=self._config.version,
        )

        # Generate first question via LLM (errors propagate here)
        system_prompt = build_system_prompt(self._config, session)
        user_prompt = build_user_prompt("/start")
        llm_resp = await self._llm.complete(system_prompt, user_prompt)

        return session, llm_resp.user_message

    async def process_message(
        self, session: Session, user_message: str
    ) -> tuple[Session, str]:
        """Process a user message and advance the state machine."""
        current_node = self._config.get_node(session.current_node_id)
        if current_node is None:
            raise ValueError(
                f"Node '{session.current_node_id}' not found in config"
            )

        system_prompt = build_system_prompt(self._config, session)
        user_prompt = build_user_prompt(user_message)

        # Try to get a valid response from LLM (1 attempt + 1 retry)
        try:
            llm_resp = await self._llm.complete(system_prompt, user_prompt)
        except LLMError:
            logger.exception("LLM call failed")
            return session, _LLM_ERROR_MSG

        # Handle clarification
        if llm_resp.needs_clarification:
            if session.clarification_count >= self._max_clarifications:
                return self._fallback(session, user_message)
            return session.increment_clarification(), llm_resp.user_message

        # Validate response
        validation = validate_response(
            llm_resp, self._config, session.current_node_id
        )

        if not validation.is_valid:
            logger.warning("Invalid LLM response: %s. Retrying...", validation.errors)
            try:
                llm_resp = await self._llm.complete(system_prompt, user_prompt)
            except LLMError:
                logger.exception("LLM retry failed")
                return self._fallback(session, user_message)

            validation = validate_response(
                llm_resp, self._config, session.current_node_id
            )
            if not validation.is_valid:
                logger.warning("Retry also invalid: %s. Using fallback.", validation.errors)
                return self._fallback(session, user_message)

        # Validate score updates against bounds
        score_errors = validate_score_updates(
            llm_resp.score_updates,
            self._config.scoring,
            session.scores,
        )
        if score_errors:
            logger.warning("Invalid score updates: %s. Using fallback.", score_errors)
            return self._fallback(session, user_message)

        # Advance session
        new_session = session.advance(
            next_node_id=llm_resp.next_node_id,
            score_updates=llm_resp.score_updates,
            user_answer=user_message,
            assistant_message=llm_resp.user_message,
        )

        # Check if we reached a terminal node
        next_node = self._config.get_node(llm_resp.next_node_id)
        if next_node and next_node.type == NodeType.TERMINAL:
            new_session = new_session.complete()

        return new_session, llm_resp.user_message

    def _fallback(
        self, session: Session, user_message: str
    ) -> tuple[Session, str]:
        """Fallback: use first routing rule and first scoring rule."""
        current_node = self._config.get_node(session.current_node_id)
        if current_node is None:
            raise ValueError(
                f"Node '{session.current_node_id}' not found in config"
            )

        # Use first routing rule
        fallback_next = current_node.routing[0].next

        # Use first scoring rule's update (or empty)
        fallback_scores = (
            current_node.scoring_rules[0].update if current_node.scoring_rules else {}
        )

        new_session = session.advance(
            next_node_id=fallback_next,
            score_updates=fallback_scores,
            user_answer=user_message,
            assistant_message="(fallback applied)",
        )

        next_node = self._config.get_node(fallback_next)
        if next_node and next_node.type == NodeType.TERMINAL:
            new_session = new_session.complete()

        fallback_msg = (
            "I'll move on to the next question. "
            "You can always come back to refine your answers."
        )
        return new_session, fallback_msg
