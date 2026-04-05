# Tech Context

## Репозиторий

| Путь | Назначение |
|------|------------|
| **`kya-backend/`** | Основной Python/Node бэкенд: `app/main.py`, `core/config.py`, `api/endpoints.py`, `services/gemini.py`, `services/solana.py`, `schemas/models.py`, `mcp/server.py`, `app/node/` |
| **`kya-backend/idl/kya_program.json`** | IDL Anchor (плейсхолдер → артефакт от Человека 1) |
| **`memory-bank/`** | Только у **корня репозитория** (правила workspace) |
| **`programs/kya-decisions/`** | Rust / Anchor программа |
| Корень `requirements.txt` | Legacy; актуально — **`kya-backend/requirements.txt`** |

## Стек

- **FastAPI**, **Pydantic Settings**, **Uvicorn**
- **Google Gemini** — `google-genai`, сервис в `app/services/gemini.py`
- **anchorpy 0.20** + **solana 0.34–0.35** (явный pin в `requirements.txt`; 0.36 ломает anchorpy), `app/services/solana.py`
- **mcp** — день 3, `app/mcp/server.py`
- **Node** — `kya-backend/app/node/` (опциональный gateway)

## Переменные окружения

Файл **`.env`** в каталоге **`kya-backend/`** (см. `kya-backend/.env.example`): `GEMINI_API_KEY`, `GEMINI_MODEL`, `SOLANA_RPC_URL`, `SOLANA_PRIVATE_KEY`, опц. `KYA_KEYPAIR_PATH`, `KYA_PROGRAM_ID`, `KYA_IDL_PATH`.

## Запуск API

```bash
cd kya-backend
uvicorn app.main:app --reload
```

## Дизайн

- `memory-bank/creative/gemini_design.md`
