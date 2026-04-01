# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HEA (Health Assessment Engine) — a Telegram bot for conducting micro health assessments. Uses an **Agentic State Machine** pattern: deterministic code controls state transitions, LLM only classifies user responses into predefined categories via structured output.

## Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the bot
python -m hea

# Run all tests
pytest

# Run tests with coverage
pytest --cov

# Run a single test file
pytest tests/test_orchestrator.py

# Run a single test
pytest tests/test_orchestrator.py::test_function_name -v
```

## Documentation Lookups

When you need documentation for any library or API, use the Context7 MCP server to fetch up-to-date docs instead of relying on training data.

## Architecture

**Pattern:** Code owns state transitions; LLM is a constrained semantic classifier (structured JSON output only). Assessment logic is defined in YAML configs (`assessments/`), editable by medical specialists without code changes.

**Data flow:** User message → Telegram (aiogram) → Rate limiter → Load session (SQLite) → Orchestrator → Build prompt (current node only, not full graph) → LLM call (OpenRouter/httpx) → Validate response → Update scores & advance state → Save session → Reply

**Key modules under `src/hea/`:**

- `orchestrator/engine.py` — State machine core. Handles message processing, LLM calls, validation, clarification tracking, and fallback logic (first routing/scoring rule on validation failure). 1-retry on LLM validation failure.
- `orchestrator/validator.py` — Validates LLM responses: next_node exists and is reachable, matched_category is valid, score updates within bounds.
- `llm/client.py` — OpenRouter HTTP client with JSON schema enforcement for structured output.
- `llm/prompt_builder.py` — Constructs system prompts with current node context, scoring/routing rules, history (last 3 entries), and compliance constraints.
- `models/` — Immutable Pydantic models (frozen). `Session` uses `model_copy()` for state transitions.
- `models/llm.py` — `LLMResponse` schema: reasoning, matched_category, score_updates, next_node_id, user_message, needs_clarification.
- `assessment/loader.py` — Loads YAML config → `AssessmentConfig` with graph validation (unique IDs, routing references).
- `storage/repository.py` — Async SQLite repository. Sessions stored as JSON (chat_id PK).
- `bot/handlers.py` — Telegram handlers + `setup()` initializer. Rate limiting and message length validation.
- `bot/formatting.py` — HTML report generation, emoji formatting, disclaimer.
- `settings.py` — Pydantic BaseSettings from `.env`.

## Assessment YAML Structure

Each assessment defines: nodes (question/terminal), scoring categories with bounds (min/max), scoring rules (category → score delta per matched answer), and routing rules (category → next node). See `assessments/cardio_risk_v1.yaml`.

## Configuration

Copy `.env.example` to `.env`. Required: `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`. Default LLM model: `google/gemini-3.1-flash-lite-preview` via OpenRouter.

## Testing Notes

- `pytest-asyncio` with `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`.
- Coverage excludes `__main__.py` and `bot/*` (Telegram handlers tested manually).
- LLM calls are mocked via `AsyncMock` with `side_effect`.
- Specs are in Russian (`SPEC.md`, `PLAN.md`). Code and tests are in English.
