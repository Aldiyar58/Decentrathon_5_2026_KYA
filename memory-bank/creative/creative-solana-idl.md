# CREATIVE / BUILD: Solana IDL (kya) — PDA, инструкции, интеграция verify

## Источник

IDL: `kya-backend/idl/kya_program.json` (инструкции `registerAgent`, `logIntent`; аккаунты `kya::AgentRecord`, `kya::IntentLog`).

## Решение по PDA seeds (допущение до сверки с Rust)

On-chain seeds в IDL не описаны. В **`app/services/solana.py`** зафиксировано:

| PDA | Seeds |
|-----|--------|
| `agentRecord` | `[b"agent", owner_pubkey]` |
| `intentLog` | `[b"intent_log", agent_record_pubkey]` |

Если `register_agent` / `log_intent` падают с ошибкой аккаунтов — **сверить seeds в программе Anchor** и обновить константы `SEED_AGENT` / `SEED_INTENT_LOG`.

## Инструкции

- **`register_agent_on_chain()`** — `program.methods["register_agent"]` с `agent_record`, `owner`, `system_program` (solders `SYS_PROGRAM_ID`).
- **`log_intent_on_chain(intent_id, decision, is_approved)`** — `log_intent` с PDAs + owner; `decision` усечён до 512 символов (лимит on-chain / `DecisionTooLong`).
- **`get_agent_info()`** / **`fetch_agent_record_for_owner`** — `program.account[<ключ>].fetch(agent_pda)`; ключ **`AgentRecord`** если есть в IDL, иначе **`kya::AgentRecord`**. Возвращается словарь с **`trust_level`**, `total_logs`, `owner`, `agent_record_address`, …
- **HTTP:** `GET /agents/{agent_id}` — `agent_id` = base58 **owner** pubkey.

## Поток verify (HTTP)

После ответа Gemini, если заданы **`KYA_PROGRAM_ID`** и ключ (**`SOLANA_PRIVATE_KEY`** или **`KYA_KEYPAIR_PATH`**), вызывается **`log_intent_on_chain`** с:

- `intent_id`: случайный `u64`;
- `decision`: строка из Gemini (`approve` / `reject` / `escalate`);
- `is_approved`: `decision == "approve"`.

При ошибке chain — ответ Gemini сохраняется, `intent_log_signature` = `null`, ошибка в лог.

## Зависимости

- **anchorpy 0.20** совместим с **solana 0.34–0.35** (не 0.36+ из‑за `solana.transaction`).
- Возможен конфликт версий **websockets** с `google-genai`; при сбоях — подобрать версию, удовлетворяющую обоим пакетам.
