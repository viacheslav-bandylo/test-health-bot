"""Telegram bot message handlers."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from hea.assessment.loader import load_assessment
from hea.bot.rate_limiter import RateLimiter, validate_message_length
from hea.llm.client import LLMClient
from hea.models.assessment import AssessmentConfig
from hea.models.session import SessionState
from hea.orchestrator.engine import Orchestrator
from hea.report.text_report import generate_report
from hea.settings import Settings
from hea.storage.repository import SessionRepository

logger = logging.getLogger(__name__)

router = Router()

# Module-level state set during setup
_orchestrator: Orchestrator | None = None
_repo: SessionRepository | None = None
_config: AssessmentConfig | None = None
_llm_client: LLMClient | None = None
_rate_limiter: RateLimiter | None = None
_max_message_length: int = 500


async def setup(
    settings: Settings,
) -> tuple[Dispatcher, Bot, SessionRepository, LLMClient]:
    """Initialize bot components and return resources for cleanup."""
    global _orchestrator, _repo, _config, _llm_client, _rate_limiter, _max_message_length

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    # Load assessment from configurable path
    _config = load_assessment(settings.assessment_path)

    # Initialize storage
    _repo = SessionRepository(settings.database_path)
    await _repo.initialize()

    # Initialize LLM client
    _llm_client = LLMClient(settings)

    # Create orchestrator
    _orchestrator = Orchestrator(
        config=_config,
        llm_client=_llm_client,
        max_clarifications=settings.max_clarifications_per_node,
    )

    # Rate limiter
    _rate_limiter = RateLimiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    _max_message_length = settings.max_message_length

    return dp, bot, _repo, _llm_client


def _require_setup() -> tuple[Orchestrator, SessionRepository, AssessmentConfig]:
    """Return initialized components or raise RuntimeError."""
    if _orchestrator is None or _repo is None or _config is None:
        raise RuntimeError("Bot not initialized. Call setup() first.")
    return _orchestrator, _repo, _config


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Handle /start command — begin a new assessment."""
    orchestrator, repo, _cfg = _require_setup()

    if message.chat is None:
        return

    chat_id = message.chat.id

    if _rate_limiter and not _rate_limiter.is_allowed(chat_id):
        await message.answer("Too many requests. Please wait a moment.")
        return

    # Delete any existing session
    await repo.delete(chat_id)

    session, greeting = await orchestrator.start_session(chat_id=chat_id)
    await repo.save(session)
    await message.answer(greeting)


@router.message()
async def handle_message(message: Message) -> None:
    """Handle user messages during assessment."""
    orchestrator, repo, config = _require_setup()

    if message.chat is None or message.text is None:
        return

    chat_id = message.chat.id

    if _rate_limiter and not _rate_limiter.is_allowed(chat_id):
        await message.answer("Too many requests. Please wait a moment.")
        return

    session = await repo.get_by_chat_id(chat_id)
    if session is None:
        await message.answer("Please send /start to begin an assessment.")
        return

    if session.state == SessionState.COMPLETED:
        await message.answer(
            "Your assessment is already completed. Send /start to begin a new one."
        )
        return

    text = validate_message_length(message.text, _max_message_length)

    new_session, response_text = await orchestrator.process_message(session, text)
    await repo.save(new_session)

    if new_session.state == SessionState.COMPLETED:
        report = generate_report(config, new_session)
        await message.answer(f"{response_text}\n\n{report}")
    else:
        await message.answer(response_text)
