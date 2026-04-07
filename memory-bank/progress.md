# Memory Bank: Progress

## Архив

**Завершённая веха (2026-04-06):** [archive-kya-backend-2026-04.md](archive/archive-kya-backend-2026-04.md) — Solana 0.36+, новый IDL (IntentRecord, logger_authority, u8 decision), эндпоинты, MCP, тесты.

**Phase 6 (2026-04-07):** [archive-phase6-cloud-mcp-sse.md](archive/archive-phase6-cloud-mcp-sse.md) — MCP по HTTP/SSE (`/mcp`), `SseServerTransport`, `X-API-KEY`, `mcp_tool_handlers`, `README_MCP.md`.

---

## Snapshot (2026-04) — кратко

### Статус эндпоинтов (новый IDL)

| Эндпоинт | Статус |
|----------|--------|
| **`POST /agents/register`** | `agent_name`, `max_amount`, опционально **`description`** и `logger_authority`. При непустом `description`: сохранение миссии в памяти, вызов Eliza **`POST {ELIZA_API_URL}/agents/{agent_id}/set`** с `character` (bio/lore + `settings.secrets` KYA MCP). Ответ: **`eliza_status`** (`skipped` / `ok` / `error`), **`eliza_agent_id`**, **`eliza_error`**. |
| **`POST /verify-intent`** | Опционально **`agent_id`** (owner base58) — подтягивается миссия из in-memory store; в system prompt Gemini добавляется блок mission alignment (**reject** = on-chain **1**, если интент вне миссии). Далее как раньше: `log_intent`, u8 decision, `amount`, `destination`, `intent_id`. |

### Архитектура логов

- **Отказ от общего вектора логов:** каждый интент — отдельный аккаунт **`IntentRecord`**.
- **Семена PDA:** `[b"intent", agent_record_pda, intent_id_u64_le_8bytes]`.
- **`logger_authority`** — **обязательный подписант** для инструкции **`log_intent`** (в коде: кошелёк из `KYA_LOGGER_*` или тот же, что **owner**).

### Маппинг решения (документация / контракт)

| On-chain `u8` | Смысл    | Строка Gemini |
|---------------|----------|----------------|
| **0**         | Approve  | `approve`      |
| **1**         | Reject   | `reject`       |
| **2**         | Escalate | `escalate`     |

Код: `gemini_decision_to_u8` / `decision_u8_to_label` в **`app/services/solana.py`**.

### Прочее

| Area | Status |
|------|--------|
| IDL | **`idl/kya_program.json`** — legacy для **anchorpy**; **`idl/kya_program.anchor030.json`** — экспорт Anchor 0.30+ |
| API | **`GET /agents/{id}/logs`** — до 20 **IntentRecord**, перебор id от **`total_logs`** вниз (эвристика) |
| Настройки | `KYA_LOGGER_AUTHORITY`, `KYA_LOGGER_PRIVATE_KEY`, `KYA_LOGGER_KEYPAIR_PATH` (опционально; без них logger = owner) |
| Eliza / MCP в character | **`ELIZA_API_URL`**, **`ELIZA_API_KEY`** (опц.), **`KYA_MCP_SSE_URL`**, **`KYA_MCP_API_KEY`** (ключ для заголовка `X-API-KEY` со стороны Eliza); сервер MCP по-прежнему **`KYA_MCP_API_KEYS`**. |
| Хранилище миссий | **`app/services/agent_mission_store.py`** — `agent_id` → `description` (процесс; v1 без Redis). |

## Запуск MCP

- **stdio (локально):** из корня репозитория: `python -m app.mcp.server`
- **HTTP/SSE (облако):** поднять FastAPI (`uvicorn app.main:app`); префикс **`/mcp`**:
  - `GET /mcp/sse` — SSE (заголовок **`X-API-KEY`** обязателен, если задан `KYA_MCP_API_KEYS`);
  - `POST /mcp/messages/?session_id=…` — JSON-RPC (тот же ключ);
  - несколько ключей в **`KYA_MCP_API_KEYS`** через запятую или `;`.
- Реализация: **`app/api/mcp.py`** (`SseServerTransport`), общая логика tools — **`app/services/mcp_tool_handlers.py`**.
- Пользовательская инструкция: **`README_MCP.md`** (в корне репозитория).

## Тесты

`pytest -q` — **17 passed**; `pytest.ini`: `-p no:anchorpy`.
