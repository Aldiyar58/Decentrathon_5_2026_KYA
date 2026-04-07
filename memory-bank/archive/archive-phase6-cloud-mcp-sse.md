# TASK ARCHIVE: Phase 6 — Cloud MCP (HTTP/SSE)

## METADATA

| Field | Value |
|--------|--------|
| **Task ID** | `phase6-cloud-mcp-sse` |
| **Дата архивации** | 2026-04-07 |
| **Complexity** | Level 3 (feature) |
| **Статус** | COMPLETE |

## SUMMARY

Добавлен сетевой MCP поверх существующего FastAPI: транспорт **SSE** (`SseServerTransport` из пакета `mcp`), префикс **`/mcp`**, защита **`X-API-KEY`** через переменную **`KYA_MCP_API_KEYS`**. Логика инструментов вынесена в **`app/services/mcp_tool_handlers.py`** и используется и **stdio** MCP (`python -m app.mcp.server`), и HTTP-слоем. Документация для пользователей: **`README_MCP.md`**, техконтекст обновлён в **`memory-bank/techContext.md`**.

## REQUIREMENTS

- Переход с единственного **stdio** MCP на вариант, пригодный для **облачного хостинга** (удалённые агенты).
- Эндпоинты **`/sse`** и **`/messages/`** (в составе mount **`/mcp`**).
- Инструменты HTTP MCP: **`verify_intent`**, **`register_agent`**, **`get_agent_info`**; stdio сохраняет также **`get_credential`**.
- **API Key** для внешних вызовов к `/mcp`.
- Интеграция **SolanaService** / **Gemini** без третьего дублирования бизнес-логики относительно REST.

## IMPLEMENTATION

| Компонент | Назначение |
|-----------|------------|
| `app/api/mcp.py` | `SseServerTransport("/messages/")`, `GET /sse`, `Mount /messages/`, `McpApiKeyMiddleware`, `FastMCP` + `MCPServer.run` на streams |
| `app/services/mcp_tool_handlers.py` | `verify_intent_handler`, `register_agent_handler`, `get_agent_info_handler`, `get_credential_handler` |
| `app/mcp/server.py` | stdio: те же хендлеры + tool `get_credential` |
| `app/main.py` | `app.mount("/mcp", mcp_asgi_app)` |
| `app/core/config.py` | `kya_mcp_api_keys` → env `KYA_MCP_API_KEYS` |
| `requirements.txt` | явный pin `sse-starlette` |
| `.env.example` | комментарий по `KYA_MCP_API_KEYS` |
| `README_MCP.md` | URL, tools, пример Claude Desktop через `mcp-remote` |

**Технические детали:** DNS-rebinding в транспорте отключён (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`); авторизация на уровне ASGI middleware до Starlette MCP app.

## TESTING

- `tests/test_mcp_http.py`: 401 при пустом списке ключей, отсутствии/неверном `X-API-KEY`; POST с валидным ключом и неизвестной `session_id` → 404.
- `tests/test_api.py`: поправка тела **`POST /agents/register`** (обязательное `description` в схеме).
- Полный прогон: **`pytest -q`** — 15 passed (`pytest.ini`: `-p no:anchorpy`).

## LESSONS LEARNED

- Один процесс с REST упрощает деплой; SSE требует настройки **таймаутов** на reverse proxy.
- Клиенты вроде **Claude Desktop** часто нуждаются в **`mcp-remote`** для URL; статический **`X-API-KEY`** передаётся через **`--header`**.
- Зависимость от **`FastMCP._mcp_server`** — точка внимания при обновлениях SDK.
- См. подробнее: **`memory-bank/reflection/reflection-phase6-cloud-mcp-sse.md`**.

## REFERENCES

| Документ | Путь |
|----------|------|
| Рефлексия | [reflection-phase6-cloud-mcp-sse.md](../reflection/reflection-phase6-cloud-mcp-sse.md) |
| План (Phase 6 в tasks, снят в архив) | История в git / этот архив |
| Пользовательская инструкция | `README_MCP.md` (корень репозитория) |
| Техконтекст | [techContext.md](../techContext.md) |

## ОТЛОЖЕНО / FOLLOW-UP

- Полный e2e с реальным удалённым MCP-клиентом на прод-URL.
- Возможная миграция на **streamable HTTP** по мере зрелости клиентов.
- Опционально: `Authorization: Bearer` в дополнение к `X-API-KEY`.
