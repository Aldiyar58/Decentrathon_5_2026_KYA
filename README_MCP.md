# KYA MCP — подключение и инструменты

MCP доступен двумя способами:

| Режим | Когда использовать |
|--------|---------------------|
| **stdio** | Локально, Cursor/Claude Desktop без сети: `python -m app.mcp.server` |
| **HTTP + SSE** | Облако или удалённые агенты: тот же процесс, что и FastAPI, префикс `/mcp` |

Подробности реализации: `app/api/mcp.py`, `app/services/mcp_tool_handlers.py`, stdio: `app/mcp/server.py`.

---

## URL эндпоинтов (HTTP/SSE)

Поднимите API, например:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Базовый URL (замените хост и порт):

| Назначение | Метод | Путь |
|------------|--------|------|
| Установка SSE-сессии MCP | **GET** | `https://<host>/mcp/sse` |
| JSON-RPC сообщения клиента | **POST** | URL из первого SSE-события `endpoint` (вида `https://<host>/mcp/messages/?session_id=<uuid_hex>`) |

**Аутентификация:** заголовок **`X-API-KEY`** на **оба** запроса (SSE и POST). Ключи задаются в переменной окружения **`KYA_MCP_API_KEYS`** (несколько значений через запятую `,` или `;`). Если переменная пустая, все запросы к `/mcp` получают **401**.

Локально по HTTP (без TLS):

```text
GET http://127.0.0.1:8000/mcp/sse
Header: X-API-KEY: <ваш_ключ>
```

---

## Инструменты (tools)

Ответы инструментов — **JSON-строка** (текстовое содержимое результата tool call).

### HTTP MCP (`app/api/mcp.py`)

| Имя | Описание | Аргументы |
|-----|------------|-----------|
| **`verify_intent`** | Анализ интента через Gemini; при `record_on_chain=true` и настроенной цепочке — запись `log_intent` в Solana. | `intent_text` (string), `context_json` (string, optional), `record_on_chain` (bool, default `true`), `amount` (int, default `0`), `destination` (string, optional, base58 pubkey) |
| **`register_agent`** | Регистрация агента on-chain. | `agent_name` (string), `max_amount` (int), `logger_authority` (string, optional, base58) |
| **`get_agent_info`** | Чтение **AgentRecord** для кошелька сервера (`SOLANA_PRIVATE_KEY` / `KYA_KEYPAIR_PATH`). | *(нет аргументов)* |

### stdio MCP (`python -m app.mcp.server`)

Те же три инструмента, плюс:

| Имя | Описание | Аргументы |
|-----|------------|-----------|
| **`get_credential`** | **AgentRecord** по произвольному owner (base58). | `owner_pubkey` (string) |

---

## Пример: Claude Desktop → удалённый SSE через `mcp-remote`

Claude Desktop обычно запускает MCP как **stdio**-процесс. Для подключения к вашему **URL** используйте прокси **[mcp-remote](https://www.npmjs.com/package/mcp-remote)** (`npx`, Node 18+).

Файл конфигурации:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

После правок **полностью перезапустите** Claude Desktop.

### Прод (HTTPS)

```json
{
  "mcpServers": {
    "kya-remote": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://YOUR_DOMAIN/mcp/sse",
        "--transport",
        "sse-only",
        "--header",
        "X-API-KEY:${KYA_MCP_HEADER}"
      ],
      "env": {
        "KYA_MCP_HEADER": "paste-your-api-key-here"
      }
    }
  }
}
```

В `args` для Windows важно **не ставить пробелы вокруг `:`** в строке заголовка; сам ключ безопасно держать в `env` (как выше).

### Локально (HTTP, порт 8000)

Для `http://127.0.0.1` у `mcp-remote` нужен флаг **`--allow-http`**:

```json
{
  "mcpServers": {
    "kya-local": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8000/mcp/sse",
        "--allow-http",
        "--transport",
        "sse-only",
        "--header",
        "X-API-KEY:${KYA_MCP_HEADER}"
      ],
      "env": {
        "KYA_MCP_HEADER": "your-local-dev-key"
      }
    }
  }
}
```

В `.env` приложения задайте тот же ключ в **`KYA_MCP_API_KEYS`**.

### Замечания

- Если прокси пытается открыть **OAuth** в браузере, а ваш сервер отдаёт только **401 без OAuth**, проверьте, что **`X-API-KEY`** уходит на каждый запрос (см. `--header` и логи `mcp-remote` с флагом `--debug`).
- Альтернатива без сети: в Desktop можно подключить **stdio**-сервер командой `python -m app.mcp.server` (из корня репозитория, с активированным venv и зависимостями).

---

## Cursor

Прямой SSE поддерживается в новых версиях Cursor; см. [документацию Cursor MCP](https://docs.cursor.com/context/model-context-protocol). Для OAuth-ориентированных удалённых серверов также используют `mcp-remote` по аналогии с примером выше.
