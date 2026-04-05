# Memory Bank: Progress

## Snapshot

| Area | Status |
|------|--------|
| Solana | `solana.py`: seeds **`b"agent"`**, **`b"intent_log"`**; `register_agent_on_chain`, `log_intent_on_chain`; `get_agent_info` / `fetch_agent_record_for_owner` через **`program.account[ключ].fetch()`**, ключ **`AgentRecord`** или **`kya::AgentRecord`** (автовыбор) |
| API | `POST /verify-intent` → Gemini → **`log_intent_on_chain`**; **`GET /agents/{agent_id}`** (owner pubkey base58); **`POST /agents/register`** |
| MCP | `app/mcp/server.py`: **FastMCP**, stdio (`mcp.run(transport="stdio")`), tools **`verify_intent`**, **`get_credential`**, **`register_agent`** |
| Тесты | `pytest tests/ -v` — **6 passed** (Python 3.13) |

## Запуск MCP

Из каталога **`kya-backend`** (чтобы подтянулся `.env` из `config.py`):

```bash
python -m app.mcp.server
```

В Cursor: command — тот же `python`, args `-m app.mcp.server`, cwd — `kya-backend`.

## Зависимости

`requirements.txt`: `solana>=0.34,<0.36`, `anchorpy`, `mcp>=1.0.0`; `pytest.ini`: `-p no:anchorpy`.
