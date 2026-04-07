# TASK REFLECTION: Phase 6 — Cloud MCP (SSE)

## Summary

Реализован сетевой MCP поверх того же FastAPI-приложения, что и REST API: транспорт **HTTP + SSE** через `SseServerTransport` из пакета `mcp`, маршруты под префиксом **`/mcp`**, защита **`X-API-KEY`** (`KYA_MCP_API_KEYS`). Логика инструментов вынесена в **`app/services/mcp_tool_handlers.py`** и переиспользуется stdio-сервером (`python -m app.mcp.server`) и HTTP-слоем.

## What went well

- **Один процесс с API:** `app.mount("/mcp", mcp_asgi_app)` упрощает деплой и секреты (один сервис, один набор env).
- **Корректные пути для клиента:** транспорт инициализируется с endpoint **`/messages/`** при mount внутреннего Starlette на **`/mcp`**, так что в SSE-событии `endpoint` указывает на **`/mcp/messages/?session_id=…`** (учёт `root_path`).
- **Явное использование `SseServerTransport`:** совпадает с документацией SDK и упрощает рассуждение о двух ASGI-обработчиках (GET SSE + POST messages).
- **Разделение auth:** API Key авторизует только доступ к хосту; on-chain подпись по-прежнему от серверных Solana-ключей.

## Challenges

- **Claude Desktop не подключается к URL напрямую** в классической схеме: нужен мост (**`mcp-remote`**) или локальный stdio.
- **`mcp-remote` и OAuth:** пакет ориентирован на удалённые серверы с OAuth; для KYA только **статический `X-API-KEY`** — в документации для пользователей нужно явно указать **`--header`** и при локальном HTTP флаг **`--allow-http`**.
- **Долгие SSE-соединения:** за nginx/Caddy/облачными балансировщиками нужны увеличенные read timeout для `/mcp/sse`.
- **Приватный API `_mcp_server`:** связка FastMCP → `MCPServer.run` опирается на внутреннее поле; при обновлении `mcp` возможны breaking changes (стоит следить за релизами).

## Lessons learned

- Транспорт MCP **stdio vs URL** — это разные модели доверия: для облака обязательны **TLS + API Key** (или OAuth по спецификации).
- **Общий слой хендлеров** окупается сразу при втором транспорте (stdio + SSE).
- Тесты на **401/404** без полного MCP-handshake достаточны для регрессии middleware и mount; e2e с реальным клиентом — отдельный шаг.

## Process improvements

- При смене транспорта MCP сразу фиксировать **пример клиентского конфига** (Desktop/Cursor) в корневом README — снижает вопросы по хостингу.
- В PLAN/CREATIVE явно помечать **ограничения целевых клиентов** (stdio-only Desktop vs SSE).

## Technical improvements (follow-ups)

- Рассмотреть **streamable HTTP** из актуальной спеки MCP, когда клиенты массово перейдут с legacy SSE.
- Опционально: **Bearer** в дополнение к `X-API-KEY` для единообразия с другими сервисами.
- Убрать зависимость от **`_mcp_server`**, если SDK предложит публичный API монтирования.

## Next steps

- Прогон **mcp-remote** / MCP Inspector против задеплоенного URL.
- Настройка reverse proxy (таймауты) под прод.
- По желанию: отдельный микросервис только MCP, если REST и SSE начнут конкурировать по масштабированию.
