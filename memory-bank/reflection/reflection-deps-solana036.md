# Reflection: выравнивание зависимостей (solana-py 0.36+) и аудит стека

**Task ID:** `deps-solana036`  
**Дата:** 2026-04-06  

## Summary

После перехода на **solana-py ≥ 0.36** критична связка **anchorpy ≥ 0.21** (внутри — `solders.transaction`, без `solana.transaction`). Код приложения уже использовал `solders` и `solana.rpc`. В `requirements.txt` зафиксированы **solana**, **solders**, **google-genai**; **pip check** без конфликтов, **pytest** проходит.

Дополнительно: устранены мелкие несоответствия документации/кода (MCP docstring, CORS).

## What went well

- Явная версионная связка **solana + anchorpy** документирована в `requirements.txt`.
- Импорты в `app/services/solana.py`, `endpoints.py`, `mcp/server.py` согласованы с **solders** / **solana.rpc**.
- **pytest** с `-p no:anchorpy` по-прежнему уместен (избегает плагина anchorpy в тестах).

## Challenges

- **Memory Bank (`tasks.md`)** описывает дерево **`kya-backend/`**, которого в репозитории нет: фактически **`app/`** и **`requirements.txt`** в корне **KYA-Solana**. Это источник путаницы при онбординге и в командах «из каталога kya-backend».
- Пакет **uvicorn** в requirements ограничён `<0.43.0`; при обновлении окружения pip может откатывать uvicorn (как уже было при `pip install -r`). Это не ошибка, но стоит помнить при желании взять последний uvicorn.

## Lessons learned

- Несовместимость **solana-py 0.36** с **anchorpy 0.20** проявляется на уровне **транзитивных/внутренних импортов** anchorpy, а не только кода приложения — проверять нужно и **версии зависимостей**, и **импорты в site-packages** при апгрейде.
- Дублирующие или устаревшие пути в docstring/README/memory bank быстрее ломают процесс, чем код.

## Process improvements

- При смене мажорных версий Solana-стека: `pip check`, импорт `app.main`, короткий прогон `uvicorn` + `/health`, затем **pytest**.
- Периодически сверять **tasks.md / creative** с фактической структурой репозитория.

## Technical improvements (выполнено в ходе рефлексии)

- **CORS:** список `origins` в `app/main.py` теперь реально передаётся в `CORSMiddleware` (раньше был `allow_origins=["*"]` при неиспользуемой переменной; сочетание `*` + `allow_credentials=True` для браузеров некорректно).
- **MCP:** docstring в `app/mcp/server.py` указывает запуск из **корня репозитория**, а не несуществующего `kya-backend`.

## Next steps

- Обновить **PLAN/дерево** в `memory-bank/tasks.md` под фактический корень с `app/` (или вернуть отдельную папку `kya-backend`, если это целевой стандарт).
- При появлении новых фронтенд-URL — добавлять их в `origins` в `main.py`.
- После стабилизации — команда **`/archive`** для переноса итогов в архив задачи.

## Verification log

- `pip check`: No broken requirements found.
- `pytest -q`: 6 passed.
