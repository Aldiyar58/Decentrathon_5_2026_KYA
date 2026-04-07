# Tech Context

## Репозиторий (KYA-Solana)

| Путь | Назначение |
|------|------------|
| **`app/`** | FastAPI: `app/main.py`, `app/core/config.py`, `app/api/endpoints.py`, `app/api/mcp.py`, `app/services/*.py`, `app/schemas/models.py` |
| **`app/mcp/server.py`** | MCP **stdio** (`python -m app.mcp.server`) |
| **`idl/`** | IDL Anchor для anchorpy (`kya_program.json`, опц. `kya_program.anchor030.json`) |
| **`memory-bank/`** | Memory Bank (правила workspace) |
| **`programs/`** | On-chain программа (Anchor), при наличии |
| **`requirements.txt`** | Python-зависимости корня проекта |

## Стек

- **FastAPI**, **Pydantic Settings**, **Uvicorn**
- **Google Gemini** — `google-genai`, `app/services/gemini.py`
- **Solana** — `solana>=0.36`, `solders`, `anchorpy>=0.21`, `app/services/solana.py`
- **MCP** — пакет **`mcp`**, **`sse-starlette`**
  - **stdio:** локальный процесс, `app/mcp/server.py` → `FastMCP.run(transport="stdio")`
  - **URL-based (SSE):** тот же деплой, что REST API — `app.mount("/mcp", mcp_asgi_app)` в `app/main.py`; внутри `SseServerTransport`, маршруты **`GET /mcp/sse`**, **`POST /mcp/messages/`**; общая логика tools — **`app/services/mcp_tool_handlers.py`**
- **Node** — `app/node/`, опционально

## Переменные окружения

Файл **`.env`** в **корне репозитория** (см. `.env.example`):

- **API / Solana / Gemini:** `GEMINI_API_KEY`, `GEMINI_MODEL`, `SOLANA_RPC_URL`, `SOLANA_PRIVATE_KEY`, опц. `KYA_KEYPAIR_PATH`, `KYA_PROGRAM_ID`, `KYA_IDL_PATH`, `KYA_LOGGER_*`
- **HTTP MCP:** `KYA_MCP_API_KEYS` — список ключей для заголовка **`X-API-KEY`** (через `,` или `;`); пусто → все запросы к `/mcp` с **401**

## Запуск API

Из **корня репозитория** (где лежат `app/` и `requirements.txt`):

```bash
uvicorn app.main:app --reload
```

MCP по сети: после старта доступен по префиксу **`/mcp`** (см. **`README_MCP.md`** в корне).

## MCP: stdio vs URL-based

| Аспект | stdio | URL-based (SSE) |
|--------|--------|------------------|
| Запуск | `python -m app.mcp.server` | Не отдельный процесс: вместе с `uvicorn app.main:app` |
| Клиенты | Cursor / Desktop (локальная команда) | Внешние агенты, `mcp-remote`, совместимые SSE-клиенты |
| Транспорт | stdin/stdout | **GET** SSE + **POST** JSON-RPC на URL из события `endpoint` |
| Auth | Доверие к локальному процессу | **`X-API-KEY`** + HTTPS в проде |

## Дизайн

- `memory-bank/creative/gemini_design.md`
- Рефлексия Phase 6 (SSE): `memory-bank/reflection/reflection-phase6-cloud-mcp-sse.md`
