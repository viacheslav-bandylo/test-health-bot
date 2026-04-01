# HEA - Health Assessment Engine

A Telegram bot for conducting micro health assessments using an **Agentic State Machine** pattern: deterministic code controls state transitions, while an LLM acts as a constrained semantic classifier via structured JSON output.

## How It Works

```
User message
  -> Telegram (aiogram)
  -> Rate limiter
  -> Load session (SQLite)
  -> Orchestrator (state machine)
  -> Build prompt (current node context)
  -> LLM call (OpenRouter / httpx)
  -> Validate response
  -> Update scores & advance state
  -> Save session
  -> Reply to user
```

Assessment logic is defined in YAML configs (`assessments/`), editable by medical specialists without code changes. Each assessment defines question nodes, terminal nodes, scoring categories with bounds, and routing rules.

## Prerequisites

- Python 3.12+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- An [OpenRouter](https://openrouter.ai/) API key

## Setup

1. **Clone and install:**

   ```bash
   git clone <repo-url>
   cd hea
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your credentials:

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
   | `OPENROUTER_API_KEY` | Yes | Key from openrouter.ai |
   | `OPENROUTER_MODEL` | No | LLM model (default: `google/gemini-3.1-flash-lite-preview`) |
   | `OPENROUTER_BASE_URL` | No | API base URL (default: `https://openrouter.ai/api/v1`) |
   | `DATABASE_PATH` | No | SQLite path (default: `data/sessions.db`) |
   | `LLM_TIMEOUT_SECONDS` | No | LLM call timeout (default: `15`) |
   | `MAX_CLARIFICATIONS_PER_NODE` | No | Max clarification attempts per node (default: `3`) |

3. **Run the bot:**

   ```bash
   python -m hea
   ```

## Docker

```bash
docker compose up -d
```

The bot runs as a non-root user inside the container. Session data is persisted in a named volume.

## Project Structure

```
src/hea/
  orchestrator/
    engine.py        # State machine core
    validator.py     # LLM response validation
  llm/
    client.py        # OpenRouter HTTP client
    prompt_builder.py# System prompt construction
  models/            # Immutable Pydantic models (frozen)
  assessment/
    loader.py        # YAML config -> AssessmentConfig
  storage/
    repository.py    # Async SQLite repository
  bot/
    handlers.py      # Telegram handlers, rate limiting
    formatting.py    # HTML report generation
  settings.py        # Pydantic BaseSettings from .env

assessments/
  cardio_risk_v1.yaml  # Cardiovascular risk assessment
```

## Assessment YAML Format

Assessments are defined as directed graphs in YAML:

```yaml
id: "cardio_risk"
version: "1.0"
title: "Cardiovascular Risk Assessment"

scoring:
  categories:
    - id: "cv_risk"
      name: "Cardiovascular Risk Score"
      initial: 0
      min: 0
      max: 20

nodes:
  - id: "start"
    type: "question"
    instruction: "Ask the user about their age range."
    scoring_rules:
      - category: "under_30"
        score_updates: { cv_risk: 0 }
    routing_rules:
      - category: "under_30"
        next_node: "lifestyle"
```

Medical specialists can create or modify assessments by editing YAML files -- no code changes required.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run a specific test file
pytest tests/test_orchestrator.py

# Run a specific test
pytest tests/test_orchestrator.py::test_function_name -v
```

## License

All rights reserved.
