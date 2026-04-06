# Memory Bank: Tasks — KYA Backend

## Complexity determination

| Field | Value |
|--------|--------|
| **Level** | **3** |
| **Workflow** | VAN → PLAN → CREATIVE → BUILD → REFLECT |

## Структура репозитория (PLAN — уплощение вложенности)

Код бэкенда перенесён в **`kya-backend/`** (один уровень вместо `backend/fastapi/...`).

### Решения, расходящиеся с черновиком пользователя

| Вопрос | Решение |
|--------|---------|
| **`memory-bank/` внутри `kya-backend/`** | **Нет:** по правилам workspace Memory Bank только в **`memory-bank/` у корня репозитория** (`KYA-Solana/memory-bank/`). |
| **`services/claude.py` + Anthropic** | **Нет:** стек — **Gemini**, файл **`app/services/gemini.py`**. |
| **Node внутри `app/`** | **Да:** `kya-backend/app/node/` (как просили). |

### Целевое дерево

```
KYA-Solana/
├── memory-bank/                 # только здесь (правила Cursor)
├── kya-backend/
│   ├── app/
│   │   ├── main.py              # FastAPI, include_router
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings, .env рядом с kya-backend
│   │   │   └── deps.py          # get_gemini_service
│   │   ├── api/
│   │   │   └── endpoints.py     # /health, POST /verify-intent, POST /agents/register
│   │   ├── services/
│   │   │   ├── gemini.py        # Google GenAI (BUILD)
│   │   │   └── solana.py        # anchorpy (BUILD)
│   │   ├── schemas/
│   │   │   └── models.py        # Pydantic Request/Response
│   │   ├── mcp/
│   │   │   └── server.py        # MCP entry (день 3)
│   │   └── node/                # опциональный Node gateway
│   │       ├── package.json
│   │       └── src/server.js
│   ├── idl/
│   │   └── kya_program.json     # заменить IDL от Человека 1
│   ├── .env                     # локально (не в git); шаблон — .env.example
│   ├── .env.example
│   └── requirements.txt
├── programs/kya-decisions/      # Anchor (Rust), без изменений в этом PLAN
```

### Запуск

- Из каталога **`kya-backend`**: `uvicorn app.main:app --reload`
- Установка зависимостей: `pip install -r kya-backend/requirements.txt` (в venv проекта).

---

## Стек

| Слой | Технология |
|------|------------|
| HTTP | **FastAPI** |
| LLM | **Google Gemini** (`google-genai`), `app/services/gemini.py` |
| Chain | **anchorpy**, `app/services/solana.py` |
| Схемы | **`app/schemas/models.py`** |
| MCP | **`app/mcp/server.py`** |
| Node | **`app/node/`** (опционально) |

---

## Дизайн CREATIVE

**Документ:** `memory-bank/creative/gemini_design.md` — промпт, секреты, MCP tools. В API ответа verify поле риска: **`risk_level`** (int 0–100), синхронно со схемой Gemini.

---

## Архитектура (слои)

**Целевая (после BUILD этой задачи):** `endpoints.py` → **`repositories`** (локальная БД) + **`services`** (Gemini, Solana/anchorpy + **solders**) → SDK/RPC. `mcp/server.py` — синхронизация с теми же сервисами/схемами по возможности.

---

## Аудит эндпоинтов (текущее vs требуемое)

| Сейчас | Требование | Зазор |
|--------|------------|--------|
| `POST /verify-intent` | `POST /agents/verify-intent` + сохранение копии в БД + ответ с **trust_level** после chain | Новый путь (старый оставить **deprecated** или 307 — на BUILD), добавить **IntentRepository**, после `logIntent` — **refetch AgentRecord** |
| `POST /agents/register` без тела | Тело: `owner_pubkey`, `agent_name`, `max_amount`; ответ: `agent_id`, `pda_address`, `tx_signature` | Pydantic request/response; **PDA** и **tx** из `SolanaService`; метаданные **только в БД** (см. IDL) |
| `GET /agents/{agent_id}` | «Полные данные агента» | Слияние **chain** (`AgentRecord`) + **DB** (`agent_name`, `max_amount`, timestamps) |
| — | `GET /agents/{agent_id}/logs` | Новый: чтение **IntentLog** PDA через anchorpy, сериализация `vec<IntentItem>` |
| — | `GET /intents/recent` | Новый: последние **20** записей из БД через **IntentRepository** |

### Разрыв с on-chain IDL (`idl/kya_program.json`)

- **`registerAgent`**: `args: []` — на чейне **нет** `agent_name` / `max_amount`. План: хранить их **только в локальной БД** после успешной транзакции; при расширении программы — обновить IDL и `SolanaService`.
- **`owner_pubkey` в теле register**: подписант — ключ из `.env`. Валидация: **`Pubkey.from_string(owner_pubkey)` == `Keypair.pubkey()`** иначе **400** (без смены программы нельзя регистрировать «чужого» owner тем же signer).
- **`agent_id`**: единая семантика — **base58 owner pubkey** (как сейчас в `GET /agents/{agent_id}`); `pda_address` — отдельное поле в ответах.

---

## Подтверждённая структура каталогов (факт + добавления)

```
KYA-Solana/
├── requirements.txt
├── idl/kya_program.json
├── .env / .env.example
├── memory-bank/
└── app/
    ├── main.py
    ├── api/
    │   └── endpoints.py
    ├── core/
    │   ├── config.py          # + DATABASE_URL (sqlite по умолчанию)
    │   └── deps.py            # + get_db_session, get_*_repository
    ├── db/
    │   ├── __init__.py
    │   ├── base.py            # async engine, sessionmaker, init_db / create_all
    │   └── models.py          # SQLAlchemy 2.0: AgentRow, IntentCopyRow
    ├── repositories/
    │   ├── __init__.py
    │   ├── agent_repository.py
    │   └── intent_repository.py
    ├── schemas/
    │   └── models.py          # все request/response Pydantic
    ├── services/
    │   ├── gemini.py
    │   └── solana.py          # + fetch_intent_log_for_owner; хелпер intent_log_account_key
    └── mcp/
        └── server.py          # по желанию: те же схемы/вызовы после стабилизации API
```

**Зависимости (BUILD):** `sqlalchemy[asyncio]`, `aiosqlite` (или один драйвер async для SQLite), версии **solana ≥ 0.36**, **solders**, **anchorpy ≥ 0.21** без изменения паттерна RPC.

---

## План реализации (Level 3, фазы)

### Фаза 0 — Соглашения

- [ ] Зафиксировать **`agent_id` = owner base58** в OpenAPI-описаниях.
- [ ] Таблица **agents**: `owner_pubkey` (PK/unique), `agent_name`, `max_amount`, `pda_address`, `last_register_tx`, `created_at`, `updated_at`.
- [ ] Таблица **intent_copies**: `id`, `owner_pubkey` (FK/индекс), `intent_text`, `context_json` (nullable), `decision`, `risk_level`, `is_approved`, `intent_id_on_chain` (u64), `tx_signature`, `trust_level_after` (snapshot), `created_at`.

### Фаза 1 — DB + Repository

- [ ] `app/db/base.py`: `create_async_engine`, `async_sessionmaker`, lifespan в `main.py` или startup event — `create_all`.
- [ ] `app/db/models.py`: модели под таблицы выше.
- [ ] `AgentRepository`: `upsert_after_register`, `get_by_owner_pubkey`.
- [ ] `IntentRepository`: `create_from_verify_flow`, `list_recent(limit=20)` с сортировкой по `created_at` DESC.
- [ ] `get_settings().database_url` default `sqlite+aiosqlite:///./kya.db` (путь от корня проекта или через env).

### Фаза 2 — SolanaService (solders + anchorpy 0.36)

- [ ] `intent_log_account_key(program)` — аналог `agent_record_account_key` для **`kya::IntentLog`** / `IntentLog`.
- [ ] `fetch_intent_log_for_owner(settings, owner_pubkey) -> list[dict]` — PDA intent log, `program.account[...].fetch`, нормализация полей `IntentItem` (intentId, decision, isApproved, timestamp) в JSON-совместимые типы.
- [ ] `register_agent_on_chain` без смены IDL; опционально возвращать `(signature, agent_pda)` чтобы не дублировать derive в роутере.
- [ ] После `log_intent_on_chain`: публичный метод **`fetch_agent_record_after_log`** или повторное использование `fetch_agent_record_for_owner` / `_fetch_agent_record` для **trust_level** в ответе verify.

### Фаза 3 — Pydantic (`app/schemas/models.py`)

- [ ] `RegisterAgentRequest` / `RegisterAgentResponse`.
- [ ] `VerifyAgentIntentRequest` (как текущий verify + при необходимости `owner_pubkey` если verify привязывается к агенту — по умолчанию signer wallet = owner).
- [ ] `VerifyAgentIntentResponse` — поля Gemini + `intent_log_signature`, **`trust_level`**, опционально `total_logs`.
- [ ] `AgentFullResponse` — chain + DB поля.
- [ ] `IntentItemResponse`, `IntentLogListResponse`.
- [ ] `RecentIntentRow` / `RecentIntentsResponse` для `/intents/recent`.

### Фаза 4 — HTTP (`app/api/endpoints.py`)

- [ ] `POST /agents/register` — тело, валидация owner = signer, `SolanaService.register`, `AgentRepository.upsert`, ответ с **agent_id**, **pda_address**, **tx_signature**.
- [ ] `POST /agents/verify-intent` — Gemini → при наличии chain `log_intent` → **IntentRepository.create** → refetch **trust_level**; ответ расширенный.
- [ ] `GET /agents/{agent_id}` — `AgentRepository.get` + `fetch_agent_record`; **404** если нет записи on-chain (или согласовать: только DB — зафиксировать в BUILD).
- [ ] `GET /agents/{agent_id}/logs` — `SolanaService.fetch_intent_log_for_owner`.
- [ ] `GET /intents/recent` — `IntentRepository.list_recent(20)`.
- [ ] `POST /verify-intent` — оставить как обёртку/alias с тем же хендлером или пометить deprecated в описании.

### Фаза 5 — Тесты

- [ ] Расширить `tests/conftest.py`: тестовая БД in-memory `sqlite+aiosqlite://`.
- [ ] Тесты репозиториев (CRUD + recent).
- [ ] Тесты эндпоинтов с моками `SolanaService` / Gemini где нужно.

### Creative / решения на BUILD (без отдельного CREATIVE-документа)

- Поведение **GET /agents/{agent_id}**, если агент есть в БД, но PDA ещё не создан на chain: варианты **404** vs ответ только из БД — выбрать один и задокументировать.
- Миграции: для MVP достаточно `create_all`; при росте — Alembic (отдельная задача).

---

## HTTP

| Метод | Путь | Статус |
|--------|------|--------|
| GET | `/health` | есть |
| POST | `/verify-intent` | есть → оставить/deprecated в пользу `/agents/verify-intent` |
| POST | `/agents/verify-intent` | **план** |
| POST | `/agents/register` | есть → **план**: тело + ответ |
| GET | `/agents/{agent_id}` | есть → **план**: полный агент |
| GET | `/agents/{agent_id}/logs` | **план** |
| GET | `/intents/recent` | **план** |

---

## План по дням (кратко)

- **День 1:** [x] `GeminiService` (async, `google-genai`, response schema), `POST /verify-intent`, `models.py`, `core/deps.py`, `kya-backend/.env`, тесты `pytest` (4 passed, Python 3.13).
- **День 2:** [x] `idl/kya_program.json` (полный IDL), `SolanaService` (`register_agent_on_chain`, `log_intent_on_chain`, `get_agent_info`), после `verify-intent` авто-`logIntent`; [ ] сверить **PDA seeds** с Rust при ошибках on-chain.
- **День 3:** MCP в `app/mcp/server.py`, деплой.

---

## Зависимости

См. **`requirements.txt` в корне репозитория** (`google-genai`, `solana>=0.36`, `solders>=0.21`, `anchorpy>=0.21`, `mcp`, FastAPI stack).

**Примечание (фактическая структура):** код лежит в **`KYA-Solana/app/`**, каталога **`kya-backend/`** в репозитории нет — разделы PLAN выше описывают историческое целевое дерево; запуск: из корня `uvicorn app.main:app`.

---

## Status

- [x] VAN, PLAN, CREATIVE
- [x] PLAN: новая структура `kya-backend/` (2026) — **частично устарело:** фактически плоский корень + `app/`
- [x] **PLAN (2026-04):** Repository + новые эндпоинты (`/agents/verify-intent`, расширенный register, logs, `/intents/recent`) — см. разделы «Аудит», «Структура», «План реализации» выше
- [x] BUILD — **день 1** (инфраструктура + verify-intent)
- [x] BUILD — **день 2** (часть): Solana + связка verify → `logIntent`, `/agents/register`
- [x] BUILD — день 3 (MCP stdio: `app/mcp/server.py`)
- [x] BUILD — выравнивание **solana-py 0.36+** / **anchorpy 0.21+** / **solders**
- [x] REFLECT — см. `memory-bank/reflection/reflection-deps-solana036.md`
- [x] BUILD — **on-chain only** (2026-04): `POST /agents/register` с `agent_name`/`max_amount` в инструкцию; `GET /agents/{id}` с полями AgentRecord из PDA; `GET /agents/{id}/logs` (IntentLog → `IntentEntry[]`); IDL в `idl/kya_program.json` приведён к формату **anchorpy_core**; PDA логов: **`log` + owner**
- [ ] BUILD — фазы с локальной БД (0–5 из старого плана) — **отменено по запросу** (только chain)

## Next

При смене программы — обновить **legacy IDL** вручную или скриптом из `anchor idl build`; при необходимости **`/reflect`** / **`/archive`**.
