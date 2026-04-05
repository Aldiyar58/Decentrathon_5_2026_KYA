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

`endpoints.py` → `services` → SDK; `mcp/server.py` переиспользует те же сервисы.

---

## HTTP

| Метод | Путь |
|--------|------|
| GET | `/health` |
| POST | `/verify-intent` |
| POST | `/agents/register` |

---

## План по дням (кратко)

- **День 1:** [x] `GeminiService` (async, `google-genai`, response schema), `POST /verify-intent`, `models.py`, `core/deps.py`, `kya-backend/.env`, тесты `pytest` (4 passed, Python 3.13).
- **День 2:** [x] `idl/kya_program.json` (полный IDL), `SolanaService` (`register_agent_on_chain`, `log_intent_on_chain`, `get_agent_info`), после `verify-intent` авто-`logIntent`; [ ] сверить **PDA seeds** с Rust при ошибках on-chain.
- **День 3:** MCP в `app/mcp/server.py`, деплой.

---

## Зависимости

См. **`kya-backend/requirements.txt`** (`google-genai`, `anchorpy`, `mcp`, FastAPI stack).

---

## Status

- [x] VAN, PLAN, CREATIVE
- [x] PLAN: новая структура `kya-backend/` (2026)
- [x] BUILD — **день 1** (инфраструктура + verify-intent)
- [x] BUILD — **день 2** (часть): Solana + связка verify → `logIntent`, `/agents/register`
- [x] BUILD — день 3 (MCP stdio: `app/mcp/server.py`)
- [ ] REFLECT

## Next

**`/build`** — заполнить `gemini.py`, `solana.py`, убрать `NotImplementedError` в `endpoints.py`, при необходимости вынести `deps` из endpoints в `core/deps.py`.
