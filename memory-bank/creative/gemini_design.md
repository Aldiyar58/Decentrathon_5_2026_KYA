# CREATIVE: Gemini (google-genai) — промпт, схема ответа, секреты, MCP

**Фича:** замена Claude на **Google Gemini API** через библиотеку **`google-genai`**, controlled generation (response schema), единый слой секретов для GenAI и Anchor-кошелька.

---

## CREATIVE PHASE: Gemini Prompt & JSON (Controlled Generation)

### Требования

- Модель по умолчанию: **`gemini-2.0-flash`** (настраиваемо через `GEMINI_MODEL`).
- Выход модели: **строго валидный JSON** с полями **`decision`**, **`reasoning`**, **`risk_level`** — без markdown-обёрток и пояснений вне JSON.
- Поведение: классификация/оценка **намерения и риска** по переданному тексту и опциональному контексту (KYA / Know Your Agent).

### Варианты принуждения структуры

| Вариант | Плюсы | Минусы |
|--------|--------|--------|
| **A. Native Response Schema (рекомендуется)** | Гарантия формы на стороне API; меньше парсинга | Нужна актуальная версия `google-genai` и корректная передача `GenerateContentConfig.response_schema` |
| B. JSON mode без схемы | Проще конфиг | Риск отклонений от полей |
| C. Постобработка + `model_validate` Pydantic | Гибко | Дублирование правил; модель может «сломать» JSON |

### Решение: **вариант A**

Использовать **controlled generation**: `response_mime_type="application/json"` и **`response_schema`** в конфиге генерации, согласованный с Pydantic в **`app/schemas/models.py`** (или типами рядом с `GeminiService`).

### JSON Schema (логическая модель ответа Gemini)

Используется как эталон для `response_schema` и для Pydantic:

| Поле | Тип | Описание |
|------|-----|----------|
| `decision` | string (enum) | Итоговое решение по запросу |
| `reasoning` | string | Краткое обоснование (1–5 предложений) |
| `risk_level` | integer | Числовая оценка риска **0–100** (0 = минимальный риск, 100 = максимальный) |

**Рекомендуемые enum-значения:**

- `decision`: `approve` \| `reject` \| `escalate`

`risk_level` в **JSON Schema** / SDK: `type: INTEGER`, `minimum: 0`, `maximum: 100`. В Pydantic: `Field(ge=0, le=100)`.

### Системная инструкция (system instruction)

Назначение: задать роль, ограничения и соответствие полям схемы. Текст ниже — **базовый шаблон для BUILD** (хранить в константе или конфиге, версионировать при смене политики).

```text
You are KYA (Know Your Agent), a compliance-oriented intent analyzer for autonomous agents.

Your task:
- Read the user's message and any optional structured context.
- Decide whether the described intent is acceptable under a cautious default policy (no harm, no illegal or clearly abusive goals, no credential theft or deception).
- Output ONLY a JSON object that conforms to the enforced response schema. Do not use markdown fences or prose outside JSON.

Field semantics:
- decision: "approve" if the intent is clearly acceptable; "reject" if clearly unacceptable; "escalate" if uncertain or needs human review.
- reasoning: concise justification referencing the main factors you weighed.
- risk_level: integer from 0 to 100 quantifying policy and safety risk (0 = routine/low concern; ~50 = sensitive or ambiguous; 80+ = harmful, disallowed, or high-stakes; use the full range consistently).

If context is missing, infer conservatively, prefer "escalate" over "approve" when unsure, and assign a higher risk_level when uncertain.
```

### Пользовательское сообщение (user content)

Рекомендуемый формат (один `user` turn или эквивалент):

- Блок **«Intent text»**: основной текст запроса.
- Блок **«Context (JSON)»**: опционально сериализованный JSON (метаданные агента, канал, версия политики) — строка; парсинг на стороне приложения до вызова Gemini не обязателен, но полезен для трассировки.

### Валидация после ответа

1. SDK возвращает текст/объект уже под схему — всё равно прогнать через **`GeminiVerifyResult.model_validate_json`** (Pydantic v2) или `model_validate` если API отдаёт dict.
2. При ошибке валидации: лог + HTTP 502 / tool error для MCP; не писать в Solana без валидного `decision`.

### Верификация решения

- Системная инструкция + схема покрывают поля `decision`, `reasoning`, `risk_level`.
- Регрессионные тесты: фикстуры «approve / reject / escalate» и невалидный ввод контекста.

**EXITING CREATIVE PHASE (Prompt & JSON)**

---

## CREATIVE PHASE: Secret Management (GenAI + anchorpy Wallet)

### Требования

- Секреты только из **окружения** (и `.env` локально, не в git).
- FastAPI: один **`Settings`** (`app/config.py`), создание клиентов в **`deps`** или **фабриках сервисов**, без глобального мутабельного состояния.
- **`GEMINI_API_KEY`** — для `google.genai.Client`.
- **`SOLANA_PRIVATE_KEY`** — для кошелька транзакций (anchorpy `Wallet` + `Keypair`).

### Варианты для `SOLANA_PRIVATE_KEY`

| Вариант | Плюсы | Минусы |
|--------|--------|--------|
| **A. JSON-массив байт (рекомендуется для dev)** | Стандартный формат Solana keypair (64 bytes), совместим с `Keypair.from_bytes` / из JSON | Длинная строка в env; риск утечки при логировании |
| B. Base58 secret key одной строкой | Компактно | Нужна явная документация и парсер |
| C. Путь к файлу (`KYA_KEYPAIR_PATH`) | Привычно для CLI | На проде файлов в контейнере может не быть |

### Решение

- **Продакшен-ориентированно в коде:** читать **`SOLANA_PRIVATE_KEY`** как **JSON-массив из 64 целых** (тот же вид, что в `id.json` Solana CLI), например `[1,2,...]`. Это однозначно и не требует файловой системы.
- **Опционально** (вторичный режим): если задан **`KYA_KEYPAIR_PATH`**, читать файл; иначе — `SOLANA_PRIVATE_KEY`. Приоритет задокументировать в `Settings` (например: path > env bytes).

### Инициализация Google GenAI клиента

- В `Settings`: `gemini_api_key: str`, `gemini_model: str = "gemini-2.0-flash"`.
- В `GeminiService.__init__(settings)` или фабрике:

  - `from google import genai`
  - `self._client = genai.Client(api_key=settings.gemini_api_key)`

- Не логировать ключ; при старте приложения при отсутствии ключа — fail-fast для эндпоинтов, зависящих от LLM (или явный degraded mode, если продукт решит — вынести в CREATIVE позже).

### Инициализация anchorpy `Wallet`

- Из `SOLANA_PRIVATE_KEY`: распарсить JSON → `bytes` → `Keypair.from_bytes(...)` (solders/solana API, как принято в связке с anchorpy).
- Обернуть в **`Wallet(keypair)`** для `Provider` anchorpy.
- `SOLANA_RPC_URL` — в `Settings`; `Client(SOLANA_RPC_URL)` в `SolanaService`.

### Жизненный цикл в FastAPI

- **`@lru_cache` на `get_settings()`** (Pydantic Settings) — стандартный паттерн.
- Сервисы **`GeminiService` / `SolanaService`**: либо `Depends` с созданием на запрос, либо singleton через `app.state` в `lifespan` при высокой стоимости конструкторов (для MVP достаточно Depends + один клиент на процесс при кэшировании фабрики).

**EXITING CREATIVE PHASE (Secrets)**

---

## CREATIVE PHASE: MCP Tools — сигнатуры и проброс в Gemini

### Принцип

Инструменты MCP — **тонкие адаптеры**: принимают аргументы → вызывают **`GeminiService`** и/или **`SolanaService`** (как REST), без дублирования промптов.

### Инструмент: `verify_intent`

**Назначение:** то же, что сценарий `POST /verify-intent`: анализ интента через Gemini с controlled JSON; опционально последующая запись on-chain (день 2 — через оркестратор).

**Предлагаемые аргументы (имена стабильны для клиентов MCP):**

| Аргумент | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `intent_text` | string | да | Текст намерения/запроса |
| `context_json` | string | нет | JSON-строка с доп. контекстом (агент, сессия, политика) |
| `record_on_chain` | boolean | нет | Если `true` и доступен Solana — после успешного ответа Gemini инициировать запись (идемпотентность на BUILD) |

**Возвращаемое значение (объект для MCP):**

- `decision`, `reasoning`, `risk_level` — из ответа Gemini (после Pydantic).
- Опционально: `transaction_signature` если была запись в chain.

### Инструмент: `register_agent`

**Назначение:** подготовка/валидация метаданных агента с участием Gemini (оценка риска описания), затем on-chain регистрация (день 2 по IDL).

**Предлагаемые аргументы:**

| Аргумент | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `agent_id` | string | да | Стабильный идентификатор агента (slug или внешний UUID) |
| `display_name` | string | да | Человекочитаемое имя |
| `capabilities_summary` | string | да | Текстовое описание возможностей (для Gemini и для chain-метаданных) |
| `context_json` | string | нет | Доп. JSON (организация, окружение) |

**Поток:**

1. Собрать **синтетический prompt** для Gemini: классифицировать **регистрацию агента** по тем же полям `decision` / `reasoning` / `risk_level` (можно переиспользовать ту же response schema и расширить system instruction фразой: «When the input describes agent registration, evaluate the agent profile for policy risk»).
2. Если `decision == "reject"` — **не** вызывать `SolanaService.register`; вернуть причину.
3. Если `approve` или `escalate` (политика на BUILD: эскалация блокирует или только логирует) — вызвать **`SolanaService`** для инструкции register.

**Возвращаемое значение:**

- Поля Gemini: `decision`, `reasoning`, `risk_level`.
- При успехе chain: `transaction_signature`, при необходимости `agent_pda` / адреса из IDL.

### Инструмент: `get_status` (без изменений по смыслу)

- **Без вызова Gemini**; только `SolanaService` (чтение аккаунта/PDA). Сигнатура остаётся на усмотрение IDL, например `agent_id` или `pda_address`.

### Транспорт MCP

- **Рекомендация для дня 3:** **stdio** для локального Cursor — проще секреты (наследуют env процесса), меньше сетевой атаки.
- SSE — при отдельном hosted MCP; вынести в деплой-док.

**EXITING CREATIVE PHASE (MCP)**

---

## Итоговые решения (summary)

| Тема | Выбор |
|------|--------|
| LLM | Google **Gemini** (`gemini-2.0-flash`), SDK **`google-genai`** |
| Структура ответа | Controlled generation + schema: **`decision`**, **`reasoning`**, **`risk_level`** (0–100) |
| Секреты | `GEMINI_API_KEY`; `SOLANA_PRIVATE_KEY` как JSON keypair; опционально `KYA_KEYPAIR_PATH` |
| MCP `verify_intent` | `intent_text`, опц. `context_json`, опц. `record_on_chain` → `GeminiService` (+ Solana при флаге) |
| MCP `register_agent` | `agent_id`, `display_name`, `capabilities_summary`, опц. `context_json` → Gemini затем Solana |
| Имя сервиса в коде | **`GeminiService`** (файл `gemini_service.py`); переименовать все отсылки к Claude |

## Implementation guidelines (BUILD)

1. Добавить **`google-genai`** в `kya-backend/requirements.txt` (Anthropic не используется).
2. Pydantic-модель **`VerifyIntentResponse`** (или `GeminiVerifyResult`): enum для `decision`, `int` 0–100 для `risk_level`, строка для `reasoning` — в зеркале к schema API Gemini.
3. `GeminiService.analyze_intent(intent_text, context_json: str | None) -> GeminiVerifyResult`.
4. `GeminiService.evaluate_agent_registration(...)` — отдельный метод или общий внутренний вызов с разным system/user шаблоном.
5. `.env.example`: `GEMINI_API_KEY`, `GEMINI_MODEL`, `SOLANA_RPC_URL`, `SOLANA_PRIVATE_KEY`, опц. `KYA_KEYPAIR_PATH`.
6. Тесты: мок клиента GenAI или отдельный integration test с ключом в CI secrets.
