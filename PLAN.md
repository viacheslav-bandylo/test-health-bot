# PLAN.md: Health Assessment Engine — Prototype

## Overview

Telegram-бот для проведения микро-ассессментов здоровья. Паттерн **Agentic State Machine**: детерминированный код управляет переходами состояний, LLM только классифицирует ответы пользователя в предопределённые категории.

---

## Tech Stack

| Компонент | Выбор | Почему |
|-----------|-------|--------|
| Язык | Python 3.12 | Скорость прототипирования |
| Telegram | `aiogram` 3.x | Async, стандарт для Python Telegram ботов |
| LLM | OpenRouter via `httpx` | Прямые HTTP-вызовы, без SDK |
| БД | SQLite via `aiosqlite` | Zero-config, переживает рестарты |
| Конфиг ассессментов | YAML via `pyyaml` | Читаем для медспециалистов |
| Валидация данных | `pydantic` v2 | Строгая типизация, structured output schema |
| Настройки | `pydantic-settings` | Env-based конфигурация |
| Модель по умолчанию | `google/gemini-2.5-flash-preview` | Дешёвая, быстрая, хорошо работает со structured output |

---

## Project Structure

```
hea/
├── pyproject.toml                 # Зависимости, метаданные
├── .env.example                   # Шаблон секретов
├── .env                           # Секреты (gitignored)
├── .gitignore
├── SPEC.md                        # Оригинальная спецификация
├── PLAN.md                        # Этот файл
├── README.md                      # Инструкция по запуску
│
├── assessments/                   # YAML-конфиги ассессментов (редактируют специалисты)
│   └── cardio_risk_v1.yaml        # Пример: оценка кардиоваскулярного риска
│
├── src/
│   └── hea/
│       ├── __init__.py
│       ├── __main__.py            # Точка входа: python -m hea
│       ├── settings.py            # Pydantic settings (env vars)
│       │
│       ├── models/                # Pydantic data models (immutable)
│       │   ├── __init__.py
│       │   ├── assessment.py      # AssessmentConfig, Node, ScoringRule, RoutingRule
│       │   ├── session.py         # Session, SessionState enum
│       │   └── llm.py             # LLMResponse schema
│       │
│       ├── storage/               # Персистентность сессий
│       │   ├── __init__.py
│       │   ├── repository.py      # SessionRepository (async SQLite)
│       │   └── migrations.py      # Создание таблиц
│       │
│       ├── assessment/            # Загрузка конфигов
│       │   ├── __init__.py
│       │   └── loader.py          # YAML → AssessmentConfig
│       │
│       ├── llm/                   # Интеграция с LLM
│       │   ├── __init__.py
│       │   ├── client.py          # OpenRouter HTTP client
│       │   └── prompt_builder.py  # Строит промпт для текущего узла
│       │
│       ├── orchestrator/          # Ядро системы
│       │   ├── __init__.py
│       │   ├── engine.py          # Orchestrator: стейт-машина
│       │   └── validator.py       # Валидация ответов LLM
│       │
│       ├── report/                # Генерация отчётов
│       │   ├── __init__.py
│       │   └── text_report.py     # Текстовый итог ассессмента
│       │
│       └── bot/                   # Telegram интеграция
│           ├── __init__.py
│           └── handlers.py        # Telegram message handlers
│
└── tests/
    ├── __init__.py
    ├── conftest.py                # Shared fixtures
    ├── test_models.py
    ├── test_loader.py
    ├── test_validator.py
    ├── test_orchestrator.py
    ├── test_prompt_builder.py
    └── test_text_report.py
```

---

## Key Architectural Decisions

### 1. LLM видит только текущий узел

Промпт содержит только: instruction текущего узла, категории ответов, текущие баллы, краткую историю (последние 3 ответа). НЕ весь граф. Дешевле и предсказуемее.

### 2. LLM не управляет маршрутизацией

Куда идти дальше — решает код по `next_node` из YAML-конфига. LLM только классифицирует ответ пользователя в одну из предопределённых категорий.

### 3. Structured output через response_format

LLM возвращает JSON по строгой схеме:

```python
class LLMResponse(BaseModel):
    reasoning: str            # CoT — невидим для юзера, для дебага
    matched_category: str     # Категория из scoring_rules
    score_updates: dict[str, int]  # {"cv_risk": 3}
    next_node_id: str         # Валидный узел из routing rules
    user_message: str         # Текст для отправки юзеру
    needs_clarification: bool # True = ответ неясен, остаться на узле
```

### 4. Post-validation (LLM untrusted)

Код ВСЕГДА проверяет ответ LLM:
- `next_node_id` существует в графе
- `next_node_id` доступен из текущего узла по routing rules
- `matched_category` — одна из категорий текущего узла
- `score_updates` соответствуют правилам скоринга
- Баллы не выходят за min/max

### 5. Retry + Fallback при неясных ответах

- `needs_clarification: true` → переспросить (max 3 раза)
- Исчерпаны попытки → fallback на первый вариант маршрутизации
- Невалидный ответ LLM → retry с correction prompt (1 раз), потом fallback

### 6. Immutable session state

Session — frozen Pydantic model. Обновление создаёт новый объект. Предотвращает баги мутации.

### 7. Сессия привязана к версии промпта

`assessment_id` + `assessment_version` фиксируются при старте сессии. Обновление YAML не ломает активные сессии.

---

## Assessment Config Format (YAML)

Это то, что редактирует медицинский специалист:

```yaml
id: "cardio_risk"
version: "1.0"
title: "Cardiovascular Risk Assessment"
description: "Quick screening for cardiovascular risk factors"

role_prompt: |
  You are a friendly health screening assistant. You speak in a warm,
  supportive tone. You use simple language. You NEVER diagnose conditions.
  You ONLY assess risk levels. Always respond in the user's language.

disclaimer: |
  This is not a medical diagnosis. Please consult a healthcare professional
  for medical advice.

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
    instruction: |
      Ask the user about their age range. Categories:
      - under_30: age below 30
      - 30_to_50: age between 30 and 50
      - over_50: age above 50
    scoring_rules:
      - match: "under_30"
        update: { "cv_risk": 0 }
      - match: "30_to_50"
        update: { "cv_risk": 2 }
      - match: "over_50"
        update: { "cv_risk": 4 }
    routing:
      - match: "*"
        next: "smoking"

  - id: "smoking"
    type: "question"
    instruction: |
      Ask if the user smokes. Categories:
      - never: never smoked
      - former: used to smoke but quit
      - current: currently smokes
    scoring_rules:
      - match: "never"
        update: { "cv_risk": 0 }
      - match: "former"
        update: { "cv_risk": 1 }
      - match: "current"
        update: { "cv_risk": 4 }
    routing:
      - match: "*"
        next: "exercise"

  - id: "exercise"
    type: "question"
    instruction: |
      Ask about physical activity level. Categories:
      - active: exercises 3+ times per week
      - moderate: exercises 1-2 times per week
      - sedentary: rarely or never exercises
    scoring_rules:
      - match: "active"
        update: { "cv_risk": 0 }
      - match: "moderate"
        update: { "cv_risk": 1 }
      - match: "sedentary"
        update: { "cv_risk": 3 }
    routing:
      - match: "*"
        next: "result"

  - id: "result"
    type: "terminal"
    instruction: |
      Based on the total cv_risk score, provide a summary:
      - 0-3: Low risk. Encourage maintaining healthy habits.
      - 4-7: Moderate risk. Suggest lifestyle improvements.
      - 8+: Elevated risk. Strongly recommend consulting a doctor.
```

**Ключевые решения по формату:**
- `instruction` — естественный язык, LLM адаптирует вопрос
- `match` — семантические категории, LLM классифицирует ответ
- `routing` с `"*"` — безусловный переход; условный — по match-значению
- `type: "terminal"` — сигнал завершения, генерация отчёта

---

## Data Flow

```
User → Telegram → bot/handlers.py → orchestrator/engine.py
                                          │
                        ┌─────────────────┤
                        ▼                 ▼
                  storage/            llm/client.py → OpenRouter API
                  repository.py           │
                  (SQLite)                ▼
                                    orchestrator/validator.py
                                          │
                                   ┌──────┴──────┐
                                clear          unclear
                                   │              │
                             score + advance   re-ask (retry ≤ 3)
                                   │
                             next = terminal?
                                   │
                              text_report → User
```

---

## Orchestrator State Machine

```
         ┌─────────────┐
         │   No Session │
         └──────┬───────┘
                │ /start
                ▼
         ┌─────────────┐
         │  Ask First   │◄──────────────────┐
         │  Question    │                   │
         └──────┬───────┘                   │
                │ user replies              │
                ▼                            │
         ┌─────────────┐                    │
         │  LLM Eval   │                    │
         └──┬───────┬──┘                    │
            │       │                       │
       clear│       │unclear                │
            ▼       ▼                       │
    ┌──────────┐ ┌──────────┐               │
    │ Record   │ │ Retry?   │               │
    │ Score    │ │ count<max│               │
    └────┬─────┘ └──┬────┬──┘               │
         │     yes  │    │no                │
         │          ▼    ▼                  │
         │   ┌────────────────┐             │
         │   │ Re-ask/Fallback│             │
         │   └────────────────┘             │
         ▼                                  │
  ┌──────────────┐                          │
  │ Next node    │── question ──────────────┘
  └──────┬───────┘
         │ terminal
         ▼
  ┌──────────────┐
  │ Text Report  │
  │ + Complete   │
  └──────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Project Setup + Data Models)

| # | Задача | Файл |
|---|--------|------|
| 1 | Создать `pyproject.toml` с зависимостями | `pyproject.toml` |
| 2 | `.env.example`, `.gitignore` | `.env.example`, `.gitignore` |
| 3 | Settings module (pydantic-settings) | `src/hea/settings.py` |
| 4 | Модели AssessmentConfig, Node, ScoringRule | `src/hea/models/assessment.py` |
| 5 | Модель Session, SessionState | `src/hea/models/session.py` |
| 6 | Модели LLMResponse | `src/hea/models/llm.py` |
| 7 | Unit-тесты моделей | `tests/test_models.py` |

**Проверка:** `pytest tests/test_models.py` — все тесты зелёные.

### Phase 2: Loader + Storage

| # | Задача | Файл |
|---|--------|------|
| 8 | Assessment YAML loader | `src/hea/assessment/loader.py` |
| 9 | Пример конфига | `assessments/cardio_risk_v1.yaml` |
| 10 | Тесты загрузчика | `tests/test_loader.py` |
| 11 | SQLite миграции | `src/hea/storage/migrations.py` |
| 12 | SessionRepository (async CRUD) | `src/hea/storage/repository.py` |

**Проверка:** `pytest tests/test_loader.py` — конфиг загружается и валидируется.

### Phase 3: LLM Integration

| # | Задача | Файл |
|---|--------|------|
| 13 | Prompt builder (system + user msg) | `src/hea/llm/prompt_builder.py` |
| 14 | Тесты prompt builder | `tests/test_prompt_builder.py` |
| 15 | OpenRouter HTTP client | `src/hea/llm/client.py` |

**Проверка:** `pytest tests/test_prompt_builder.py` + ручной тест вызова OpenRouter.

### Phase 4: Orchestrator (самая сложная часть)

| # | Задача | Файл |
|---|--------|------|
| 16 | Response validator | `src/hea/orchestrator/validator.py` |
| 17 | Тесты валидатора | `tests/test_validator.py` |
| 18 | Engine — стейт-машина | `src/hea/orchestrator/engine.py` |
| 19 | Интеграционные тесты (mock LLM) | `tests/test_orchestrator.py` |

**Проверка:** `pytest tests/test_orchestrator.py` — полный flow: start → 3 вопроса → отчёт.

### Phase 5: Bot + Report + Wiring

| # | Задача | Файл |
|---|--------|------|
| 20 | Text report generator | `src/hea/report/text_report.py` |
| 21 | Тесты отчёта | `tests/test_text_report.py` |
| 22 | Telegram handlers | `src/hea/bot/handlers.py` |
| 23 | Entry point (__main__.py) | `src/hea/__main__.py` |
| 24 | README | `README.md` |

**Проверка:** `python -m hea` → бот работает в Telegram.

---

## Settings (.env)

```env
TELEGRAM_BOT_TOKEN=<token from @BotFather>
OPENROUTER_API_KEY=<key from openrouter.ai>
OPENROUTER_MODEL=google/gemini-2.5-flash-preview
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DATABASE_PATH=data/sessions.db
LLM_TIMEOUT_SECONDS=15
MAX_CLARIFICATIONS_PER_NODE=3
```

---

## Risks & Mitigations

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| LLM возвращает невалидный JSON | Средняя | Retry 1 раз с correction prompt. Потом fallback |
| LLM выдумывает несуществующие категории | Средняя | Validator проверяет category_key по конфигу |
| LLM игнорирует scoring rules | Низкая | Validator сверяет score_updates с правилами узла |
| Таймаут LLM (>15s) | Низкая | Typing indicator + "Анализирую..." + retry |
| Конкурентные сообщения от одного юзера | Низкая | aiogram обрабатывает последовательно per-chat |
| Ошибки в YAML конфиге | Средняя | Pydantic валидация при загрузке (невалидные ссылки на узлы) |

---

## Success Criteria

- [ ] `python -m hea` запускает бот без ошибок
- [ ] `/start` в Telegram начинает ассессмент с дисклеймером
- [ ] Бот задаёт вопросы из YAML в правильном порядке
- [ ] Ответы на естественном языке корректно классифицируются LLM
- [ ] Баллы накапливаются корректно
- [ ] Нечёткие ответы вызывают уточняющий вопрос
- [ ] Невалидные ответы LLM перехватываются валидатором
- [ ] Финальный узел → текстовый отчёт с оценкой риска
- [ ] Рестарт бота не теряет активные сессии (SQLite)
- [ ] Новый ассессмент = новый YAML файл, zero code changes
- [ ] 80%+ test coverage на src/hea/ (кроме __main__.py и bot/handlers.py)

---

## What This Prototype Does NOT Do (Intentionally)

- Нет PDF-отчётов (только текст в Telegram)
- Нет полного compliance layer (только базовая валидация)
- Нет аутентификации (Telegram ID = identity)
- Нет поддержки нескольких ассессментов одновременно
- Нет i18n
- Нет админ-панели
- Нет rate limiting (Telegram сам лимитирует)
