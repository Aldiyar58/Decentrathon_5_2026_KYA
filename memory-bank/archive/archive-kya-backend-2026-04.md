# TASK ARCHIVE: KYA Backend — Solana 0.36+, новый IDL (IntentRecord)

## METADATA

| Field | Value |
|--------|--------|
| **Task ID** | `kya-backend-2026-04` |
| **Complexity** | Level 3 |
| **Archived** | 2026-04-06 |
| **Workflow** | VAN → PLAN → CREATIVE → BUILD → REFLECT → **ARCHIVE** |
| **Репозиторий** | `KYA-Solana` (код: `app/` у корня, не `kya-backend/`) |

## SUMMARY

Закрыт основной цикл бэкенда KYA: **FastAPI + Google Gemini + Solana/anchorpy (solana-py ≥ 0.36, solders, anchorpy ≥ 0.21)**, MCP (stdio). Выполнено выравнивание зависимостей после удаления `solana.transaction` в solana-py 0.36. Программа on-chain эволюционировала до модели **IntentRecord на интент** (без общего вектора логов), с **`logger_authority`** как обязательным подписантом **`log_intent`**, **`decision` как u8** (0/1/2), полями **`reasoning`**, **`amount`**, **`destination`**. Для **anchorpy** поддерживается **два артефакта IDL**: экспорт Anchor 0.30+ (`kya_program.anchor030.json`) и **legacy JSON** (`kya_program.json`), парсящийся `anchorpy_core`.

## REQUIREMENTS (итог)

- HTTP: `/health`, `POST /verify-intent`, `POST /agents/register`, `GET /agents/{id}`, `GET /agents/{id}/logs`.
- LLM: controlled JSON от Gemini (`decision`, `reasoning`, `risk_level`).
- Chain: регистрация агента и лог интента через **solders** + **anchorpy**; чтение **AgentRecord** и последних **IntentRecord** (эвристика по `total_logs`).
- Отдельный ключ **logger** опционально через `.env`; иначе logger = owner.
- Локальная БД / Repository по исходному плану — **отменены**; хранение on-chain only.

## IMPLEMENTATION

### Ключевые файлы

| Компонент | Путь |
|-----------|------|
| Solana / PDA / маппинг u8 | `app/services/solana.py` |
| HTTP | `app/api/endpoints.py` |
| Схемы | `app/schemas/models.py` |
| Настройки | `app/core/config.py` |
| MCP | `app/mcp/server.py` |
| IDL (anchorpy) | `idl/kya_program.json` |
| IDL (экспорт 0.30+) | `idl/kya_program.anchor030.json` |

### Архитектура on-chain (зафиксировано)

- **AgentRecord PDA:** `[b"agent", owner]`.
- **IntentRecord PDA:** `[b"intent", agent_record_pda, intent_id (u64 little-endian, 8 bytes)]`.
- **`register_agent`:** `agent_name`, `max_amount`, `logger_authority`; без создания общего лог-аккаунта при регистрации.
- **`log_intent`:** подпись **`logger_authority`**; аргументы включают **`decision: u8`**, `reasoning`, `amount`, `destination`.
- **Маппинг Gemini → chain:** `approve`→0, `reject`→1, `escalate`→2 (`gemini_decision_to_u8`).

### Зависимости

`requirements.txt`: `solana>=0.36`, `solders>=0.21`, `anchorpy>=0.21`, `google-genai>=1.0.0`, `mcp>=1.0.0`, FastAPI stack. `pytest.ini`: `-p no:anchorpy`.

## TESTING

- `pytest -q` — **10 passed** (включая `tests/test_solana_decision.py` для маппинга decision).
- Ручная проверка: импорт `app.main`, при наличии `.env` — RPC к devnet/mainnet.

## LESSONS LEARNED

1. **solana-py 0.36+** требует **anchorpy 0.21+** (Transaction из solders, не `solana.transaction`).
2. **Anchor 0.30+ IDL JSON** не парсится `anchorpy_core` без конвертации в **legacy-формат** — поддерживать оба файла или скрипт синхронизации.
3. Список всех **IntentRecord** без индексатора недоступен; используется эвристика id от **`total_logs`** вниз (до N попыток).
4. **logger_authority** на chain должен совпадать с подписантом при **`log_intent`**.

## REFERENCES

| Документ | Назначение |
|----------|------------|
| `memory-bank/reflection/reflection-deps-solana036.md` | Рефлексия по зависимостям solana-py / anchorpy |
| `memory-bank/reflection/reflection-anchor030-architecture.md` | Рефлексия по IntentRecord, u8, logger_authority |
| `memory-bank/progress.md` | Актуальный snapshot и таблица маппинга u8 |
| `memory-bank/creative/gemini_design.md` | Промпт Gemini, `risk_level` |
| `memory-bank/creative/creative-solana-idl.md` | CREATIVE по IDL (если использовался) |

---

**Статус задачи:** **COMPLETE** (архивировано).
