# Reflection: архитектура после нового IDL (IntentRecord, logger_authority)

**Task ID:** `anchor030-architecture`  
**Дата:** 2026-04-06  

## Summary

Программа KYA переведена с модели **одного аккаунта логов с вектором** на модель **отдельного аккаунта на каждый интент** (`IntentRecord`). Инструкция **`register_agent`** больше не создаёт общий лог-аккаунт; **`log_intent`** создаёт PDA **`intent_record`** с фиксированными семенами. Решение по интенту на chain кодируется **`u8`**, а не строкой. Для **`log_intent`** обязательный **подписант** — **`logger_authority`** (не обязательно совпадает с `owner`, но должен совпадать с pubkey, записанным в `AgentRecord` при регистрации).

## Ключевые изменения архитектуры

### Логи: от вектора к IntentRecord

| Было | Стало |
|------|--------|
| Один аккаунт (например `IntentLog`) с полем `logs: Vec<…>` | Каждый интент — отдельный аккаунт **`IntentRecord`** |
| Чтение: один `fetch` вектора | Чтение: выборка по известным **`intent_id`** (эвристика: id от **`total_logs`** вниз, см. `SolanaService.fetch_recent_intent_logs_for_owner`) |

**Семена PDA `IntentRecord` (как в программе и в клиенте):**

```text
[b"intent", <bytes agent_record_pda>, <intent_id as u64 little-endian, 8 bytes>]
```

Реализация: `app/services/solana.py` — `SEED_INTENT`, `derive_intent_record_pda`.

### Решение (decision) на chain: `u8`

Контракт (согласован с Rust / IDL):

| `u8` | Значение   | Строка Gemini (`decision`) |
|------|------------|----------------------------|
| **0** | Approve   | `approve`                  |
| **1** | Reject    | `reject`                   |
| **2** | Escalate  | `escalate`                 |

Маппинг в коде: **`gemini_decision_to_u8`**, обратная подпись в API — **`decision_u8_to_label`** (`app/services/solana.py`). Неизвестная строка от модели трактуется как **Escalate (2)**.

### `logger_authority`

- В **`register_agent`** в программу передаётся **`logger_authority: Pubkey`** и сохраняется в **`AgentRecord`**.
- В **`log_intent`** аккаунт **`logger_authority`** помечен как **`signer: true`** — транзакцию подписывает **ключ logger**, а не (обязательно) owner.
- В бэкенде: `Provider` + `Wallet` для `log_intent` строятся от **`_load_logger_keypair`**; если отдельный ключ не задан в `.env`, используется **тот же keypair, что и owner**.
- **Обязательное условие:** pubkey подписанта при логе **должен совпадать** с **`logger_authority` в `AgentRecord`**, иначе инструкция отклонится на chain.

Настройки: `KYA_LOGGER_AUTHORITY`, `KYA_LOGGER_PRIVATE_KEY`, `KYA_LOGGER_KEYPAIR_PATH` (`app/core/config.py`).

### IDL и anchorpy

Сырой экспорт **Anchor 0.30+** хранится в **`idl/kya_program.anchor030.json`**. Для **`Idl.from_json` (anchorpy_core)** используется **legacy-эквивалент** в **`idl/kya_program.json`** (тот же layout инструкций и типов).

## Эндпоинты (статус)

| Эндпоинт | Статус |
|----------|--------|
| **`POST /agents/register`** | Переведён: `agent_name`, `max_amount`, опционально `logger_authority` в теле; ответ с `logger_authority`, без старого `intent_log`. |
| **`POST /verify-intent`**     | Переведён: после Gemini вызывается **`log_intent`** с **`decision` u8**, `reasoning`, `amount`, `destination`; при необходимости **`intent_id`** из тела или **`total_logs + 1`**. |
| **`GET /agents/{id}/logs`**  | Переведён: список **`IntentRecord`**, не вектор в одном аккаунте. |

## What went well

- Единый источник маппинга Gemini ↔ chain в **`solana.py`** + тесты **`tests/test_solana_decision.py`**.
- Явное разделение кошельков owner / logger в конфиге без ломки сценария «один ключ».

## Challenges

- Нельзя получить **полный** список всех `IntentRecord` без индексатора — только эвристика по **`total_logs`** и последовательным id.
- Два формата IDL (0.30+ vs legacy) требуют дисциплины при обновлении программы.

## Lessons learned

- Любое изменение семян или полей структур на Rust должно синхронно отражаться в **legacy IDL** и в **Python derive/serialize**.

## Process improvements

- При обновлении программы: diff **`kya_program.anchor030.json`** → обновить **`kya_program.json`** и прогнать **`pytest`**.

## Next steps

- При непоследовательных **`intent_id`** на chain — внешний индексатор или хранение списка id off-chain.
- Опционально: эндпоинт **`deactivate_agent`** по IDL.

## Verification

- `pytest -q` (включая маппинг decision).
