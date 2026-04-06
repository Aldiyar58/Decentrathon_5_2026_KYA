# Memory Bank: Progress

## Snapshot (2026-04)

| Area | Status |
|------|--------|
| Solana | `solana.py`: PDA **`b"agent"` + owner**, **`b"log"` + owner** (как в IDL on-chain); `register_agent_on_chain(agent_name, max_amount)` с аккаунтами `agent_record`, `intent_log`, `owner`, `system_program`; `log_intent_on_chain`; `fetch_agent_record_for_owner`; **`fetch_intent_log_for_owner`** |
| IDL | `idl/kya_program.json` — формат, совместимый с **anchorpy_core** (legacy JSON); экспорт Anchor 0.30+ с отдельными discriminators в `anchor export` не парсится без конвертации |
| API | `POST /agents/register` (тело: agent_name, max_amount); `GET /agents/{agent_id}`; **`GET /agents/{agent_id}/logs`**; `POST /verify-intent` без изменений по цепочке |
| MCP | `register_agent(agent_name, max_amount)` |
| Тесты | `pytest -q` — **8 passed**; `pytest.ini`: `-p no:anchorpy` |

## Запуск MCP

Из **корня репозитория** (рядом с `app/`, `.env`):

```bash
python -m app.mcp.server
```

## Зависимости

`requirements.txt`: `solana>=0.36`, `solders>=0.21`, `anchorpy>=0.21`, `mcp>=1.0.0`, `google-genai>=1.0.0`.
