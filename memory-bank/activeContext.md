# Memory Bank: Active Context

## Current focus

**BUILD день 1 выполнен:** `kya-backend` — async `POST /verify-intent` → `GeminiService` (`google-genai`, `response_schema`, `gemini-2.0-flash`), поля ответа `decision` / `reasoning` / **`risk_level`** (0–100). `core/deps.py`, тесты `pytest` зелёные (Python 3.13).

## Immediate next step

**День 2:** `SolanaService`, реальный `idl/kya_program.json`, реализация `/agents/register`.

## Latest changes

- `kya-backend/.env` с `GEMINI_API_KEY`, `SOLANA_RPC_URL`, `SOLANA_PRIVATE_KEY` (пустые значения); корневой `.gitignore` игнорирует `.env`.
