# Memory Bank: Progress

## Snapshot (2026-04)

| Area | Status |
|------|--------|
| IDL | **`idl/kya_program.json`** — legacy для **anchorpy**; экспорт Anchor 0.30+ лежит в **`idl/kya_program.anchor030.json`** |
| Solana | **register_agent**: `agent_name`, `max_amount`, `logger_authority`; без `intent_log`. **log_intent**: PDA **`intent` + agent_record + intent_id (u64 LE)**; args **u8 decision**, reasoning, amount, destination; подпись **logger_authority** (отдельный ключ в `.env` или тот же, что owner) |
| API | **POST /verify-intent** — маппинг Gemini → u8; **POST /agents/register** — опциональный `logger_authority` в теле; **GET /agents/{id}/logs** — до 20 **IntentRecord**, перебор id от `total_logs` вниз |
| Настройки | `KYA_LOGGER_AUTHORITY`, `KYA_LOGGER_PRIVATE_KEY`, `KYA_LOGGER_KEYPAIR_PATH` (опционально) |

## Запуск MCP

Из **корня репозитория**: `python -m app.mcp.server`

## Тесты

`pytest -q` — **8 passed**; `pytest.ini`: `-p no:anchorpy`.
