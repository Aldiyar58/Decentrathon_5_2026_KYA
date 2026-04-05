# Style Guide (engineering)

- **Python:** PEP 8; типы в публичных API FastAPI; `ruff`/`black` — подключить при BUILD по согласованию команды.
- **JavaScript:** ES modules в `kya-backend/app/node`; единый стиль кавычек и `async/await`.
- **Именование:** явные имена для chain-операций (`submit_decision`, `build_record_decision_ix`).
- **Комментарии:** по делу, у границ интеграций (Gemini, Solana, MCP).
- **Секреты:** никогда в коде; только `os.environ` / config loader.
