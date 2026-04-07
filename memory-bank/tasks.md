# Memory Bank: Tasks — KYA Backend

## Статус workflow

| Фаза | Состояние |
|------|------------|
| VAN / PLAN / CREATIVE / BUILD / REFLECT / **ARCHIVE** | **COMPLETE** → **Phase 6** заархивирована |
| **Phase 7: Eliza Agent Integration** | **BUILD** — реализовано: `ElizaManager`, mission store, API/MCP/Gemini; следующий шаг: `/reflect` |
| **ARCHIVE (2026-04 backend)** | [archive-kya-backend-2026-04.md](archive/archive-kya-backend-2026-04.md) |
| **ARCHIVE (Phase 6 MCP SSE)** | [archive-phase6-cloud-mcp-sse.md](archive/archive-phase6-cloud-mcp-sse.md) |

## Текущая задача: Phase 7 — Eliza Agent Integration

### Description

Автоматический запуск **временных** ИИ-агентов на базе **Eliza (ElizaOS)** после успешной on-chain регистрации в KYA: расширение API, сервис `ElizaManager`, встраивание MCP KYA (HTTP/SSE) в конфиг персонажа, проверка соответствия интента изначальной инструкции через Gemini, жизненный цикл остановки, секреты только из `.env`.

### Complexity

| Field | Value |
|--------|--------|
| **Level** | **3** (feature: внешний рантайм + новый доменный поток + изменение политики верификации) |
| **Type** | Feature / Integration |

### Technology Stack

| Слой | Выбор |
|------|--------|
| Backend | Существующий FastAPI (`app/`) |
| Solana | Текущий `SolanaService.register_agent_on_chain` (без изменения Anchor-аргументов, если программа не расширяется) |
| LLM | Gemini (`GeminiService`) — отдельный режим/промпт для **alignment** интента с миссией |
| Eliza | ElizaOS REST (локально типично порт **3000**): создание агента (`characterJson` / `characterPath`) + **start**; точные пути — сверить с версией Eliza ([REST reference](https://docs.elizaos.ai/rest-reference)) на этапе BUILD |
| HTTP-клиент | `httpx` (async), таймауты и явные ошибки |
| Хранение миссии | v1: in-process `dict[agent_id, mission]` + абстракция интерфейса под будущий Redis/БД (multi-instance) |

### Технология — чекпоинты валидации (перед/в начале BUILD)

- [ ] Поднять Eliza локально, зафиксировать базовый URL и префикс API (`/api/...` vs `/agents/...`) из ответа сервера или документации версии.
- [ ] `curl`/интеграционный тест: **POST** создать агента с минимальным `characterJson`, затем **start**, убедиться в статусе `active`.
- [ ] Проверить, как в выбранной версии Eliza задаётся **MCP client**: URL SSE (`KYA_MCP_SSE_URL`) и заголовок **`X-API-KEY`** (значение из доверенного ключа KYA, не хардкод).
- [ ] `requirements.txt`: добавить `httpx` (если ещё нет).

### Статус Phase 7

- [x] Initialization / постановка цели (из запроса пользователя)
- [x] Planning complete (`/plan`)
- [x] Technology validation complete (smoke вручную при наличии Eliza; контракт HTTP — `POST …/agents/{id}/set`)
- [x] Implementation complete
- [x] Tests / `.env.example` — `pytest` 17 passed; переменные Eliza/MCP в примере env

---

## Implementation Plan — Phase 7

### 1. API: `POST /agents/register` и схема

**Контекст:** в `RegisterAgentRequest` уже есть поле `description`, но оно **обязательное** и **не используется** при вызове `register_agent_on_chain` (в chain уходят только `agent_name`, `max_amount`, `logger_authority`).

**План:**

1. Сделать **`description` необязательным** (`str | None`, при передаче — те же ограничения длины `1..1000`).
2. После успешного `register_agent_on_chain`:
   - если `description` пустой/`None` — ответ как сейчас (без Eliza);
   - если задан — вызвать **`ElizaManager.spawn_after_register(agent_name=..., description=..., agent_id=...)`** (см. ниже), ошибки Eliza оформить явно (502/503 + лог), не откатывая Solana-транзакцию (уже в блокчейне).
3. Расширить **`RegisterAgentResponse`** опциональными полями, например: `eliza_agent_id: str | None`, `eliza_error: str | None` — чтобы клиент видел результат spawn без обязательной зависимости от Eliza.

**MCP tool `register_agent`:** добавить опциональный параметр `description` в сигнатуру tool и прокинуть в ту же логику (общий хелпер из `mcp_tool_handlers` / сервис).

### 2. Сервис `ElizaManager` (`app/services/eliza_manager.py`)

**Ответственность:**

| Метод / блок | Поведение |
|--------------|-----------|
| `build_character_json(name, description, settings)` | Собрать объект персонажа ElizaOS: **`bio`** — краткая выжимка из `description` (можно дублировать или разбить на массив строк по правилам Eliza); **`knowledge`** — структурированные записи вида «Миссия агента: …» / bullet из `description`. |
| MCP в персонаже | Встроить в `settings` (или поля плагина MCP Eliza — **уточнить в CREATIVE/BUILD по фактической схеме**) URL **`settings.kya_mcp_sse_url`** (не хардкод `localhost` в проде) и секрет для клиента: либо выделенный **`KYA_ELIZA_MCP_API_KEY`** (рекомендуется: отдельный ключ из `KYA_MCP_API_KEYS` или отдельная env-переменная), либо согласованное имя заголовка `X-API-KEY`. |
| `register_mission(agent_id, description)` | Сохранить соответствие **`agent_id`** (owner pubkey base58 из ответа регистрации) → исходная инструкция для последующих вызовов `verify_intent`. |
| `create_and_start(name, character_dict)` | **HTTP POST** к Eliza API: создать агента с `characterJson`, затем **start**; вернуть id инстанса Eliza. |
| `stop(agent_eliza_id)` | Вызов API остановки/удаления (конкретный маршрут — по доке версии Eliza: `stop`, `DELETE`, и т.д.). |

**Зависимости:** `Settings` с новыми полями (см. §6), `httpx.AsyncClient`.

### 3. Цепочка верификации: Gemini и `verify_intent_handler`

**Цель:** при проверке интента учитывать **изначальную инструкцию** регистрации: *«Соответствует ли текущее действие агента (intent) его изначальной инструкции (description)?»*

**План:**

1. **Хранилище миссии:** при успешном spawn (или просто при `register` с непустым `description`, даже если Eliza временно недоступна — решение в CREATIVE: «только после Eliza» vs «всегда сохранять миссию») записать `agent_id → description` в реестр (v1 in-memory).
2. **Расширить вход verify:**
   - **HTTP `POST /verify-intent`:** опциональное поле `agent_id: str | None` (owner pubkey). Если задано — подгрузить сохранённую миссию; если миссии нет — не ломать контракт: работать как сейчас (только общий промпт) или вернуть `escalate` с пояснением (выбрать в CREATIVE).
   - **MCP `verify_intent`:** опциональный параметр `agent_id` (или передача через `context_json` с зарезервированным ключом — менее удобно).
3. **Gemini:** добавить отдельный **system instruction** (или второй шаг — нежелательно для латентности) для режима *alignment*: в user content передавать блоки **Original agent mission (registration description)** и **Current intent to evaluate**, плюс существующий `context_json`. Схема ответа — текущая `VerifyIntentResponse` (`approve` / `reject` / `escalate`, `reasoning`, `risk_level`), с формулировкой в промпте, что `reject`/`escalate` допустимы при несоответствии миссии.
4. Реализация в коде: либо `GeminiService.verify_intent(..., registration_mission: str | None)`, либо метод `verify_intent_with_mission(...)` — избежать дублирования парсинга ответа.

### 4. Жизненный цикл остановки агента

**Варианты (можно комбинировать):**

| Механизм | Описание |
|----------|----------|
| **A. Явный API KYA** | `POST /agents/{agent_id}/eliza/stop` (или `/agents/{agent_id}/eliza` DELETE): аутентификация тем же API key, что и остальной админ-функционал (если появится) или существующий механизм; вызов `ElizaManager.stop` + удаление записи миссии из реестра. |
| **B. Связь с Solana `max_amount`** | При операциях, которые меняют лимит/статус агента on-chain, или по **периодическому опросу** `AgentRecord` (дорого) / событию из внешнего индексатора — при «исчерпании лимита» или `is_active == false` вызывать stop. Для v1 достаточно зафиксировать в коде хук «после чтения записи агента» в отдельном джобе или в эндпоинте stop. |
| **C. TTL** | Опциональный параметр регистрации `eliza_ttl_seconds` — отложенная задача (APScheduler / фоновая корутина) для stop; усложняет прод без общего планировщика. |

**Рекомендация плана:** v1 — **A** (явный stop) + документировать **B** как follow-up при появлении индексатора.

### 5. Безопасность и `.env`

Добавить в **`Settings`** и **`.env.example`** (без секретов в репозитории):

| Переменная | Назначение |
|------------|------------|
| `ELIZA_API_BASE_URL` | Базовый URL Eliza REST, например `http://localhost:3000` |
| `ELIZA_API_KEY` | Если Eliza защищена API key / Bearer — иначе пусто |
| `KYA_MCP_SSE_URL` | Публичный URL SSE MCP для вставки в character (в dev `http://localhost:8000/mcp/sse`, в проде — реальный хост) |
| `KYA_ELIZA_MCP_API_KEY` | Ключ, которым Eliza будет ходить в KYA MCP (**отдельный** от ключей оператора, принцип least privilege; может совпадать с одним из `KYA_MCP_API_KEYS` только осознанно) |

Существующий **`KYA_MCP_API_KEYS`** остаётся источником валидации входящих запросов к `/mcp/*`.

### 6. Тестирование

- Unit: генерация `character_json` (снапшот структуры без секретов или с редоктом ключа).
- Мок `httpx`: успешный create+start, ошибка Eliza.
- API: регистрация с/без `description`; при моке Eliza — проверка полей ответа.
- `verify-intent` с `agent_id` и предзаполненной миссией — мок Gemini с проверкой, что в запрос попали mission + intent.

### 7. Зависимости и риски

- **Зависимости:** версия ElizaOS, формат character и плагина MCP.
- **Риск:** in-memory реестр миссий теряется при рестарте KYA — для прод предусмотреть смену бэкенда хранилища без смены API.
- **Риск:** двойной spawn при повторном вызове register с тем же owner — идемпотентность (ключ Eliza по `agent_id` или проверка существующего инстанса) — вынести в CREATIVE/BUILD.

---

## Creative Phases Required (Phase 7)

- [ ] **Форма `character.json` и интеграция MCP-плагина Eliza** (точные ключи `settings` / plugins).
- [ ] **Политика при отсутствии миссии в реестре** для вызова с `agent_id`.
- [ ] **Идемпотентность** регистрации + Eliza (повторные запросы).

---

## Challenges & Mitigations

| Challenge | Mitigation |
|-----------|------------|
| Документация Eliza REST расходится с версией | Зафиксировать версию в README / techContext; интеграционный smoke-тест в CI или manual checklist |
| Секрет в character уходит на сторону Eliza | Отдельный ограниченный MCP API key; ротация через `.env` |
| Multi-instance KYA | Интерфейс `MissionStore` + Redis в следующей итерации |
| Solana tx успешна, Eliza упала | Явная ошибка в ответе + retry/stop ручкой; не блокировать регистрацию в chain |

---

## Сводка доставленного ранее (живой snapshot)

- **Stack:** FastAPI, Gemini, Solana (0.36+, solders, anchorpy 0.21+), MCP **stdio** + **HTTP/SSE** (`/mcp`).
- **On-chain:** `IntentRecord`, `register_agent`, `log_intent`, `logger_authority`, `decision` u8; legacy + anchor030 IDL.
- **Репо:** `KYA-Solana/app/`, Memory Bank в `memory-bank/`.

Актуальные детали API, MCP и тестов: **`progress.md`**.

## Ссылки

| Документ | Назначение |
|----------|------------|
| [archive-kya-backend-2026-04.md](archive/archive-kya-backend-2026-04.md) | Архив вехи backend 2026-04 |
| [archive-phase6-cloud-mcp-sse.md](archive/archive-phase6-cloud-mcp-sse.md) | Архив облачного MCP (SSE) |
| [progress.md](progress.md) | Snapshot эндпоинтов / MCP / тестов |
| [reflection-phase6-cloud-mcp-sse.md](reflection/reflection-phase6-cloud-mcp-sse.md) | Рефлексия Phase 6 |
| [reflection-anchor030-architecture.md](reflection/reflection-anchor030-architecture.md) | Рефлексия по IDL |
| [reflection-deps-solana036.md](reflection/reflection-deps-solana036.md) | Рефлексия по solana-py |

## Отложено / не делалось

- Локальная БД, Repository, `/intents/recent` из БД — **отменено** (on-chain only).
- Отдельный путь `POST /agents/verify-intent` — не внедрялся; используется **`POST /verify-intent`**.
