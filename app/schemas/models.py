from pydantic import BaseModel, Field, field_validator


class VerifyIntentRequest(BaseModel):
    intent_text: str = Field(min_length=1)
    context_json: str | None = None
    agent_id: str | None = Field(
        default=None,
        description="Owner pubkey (base58); подставляет миссию из регистрации для сверки в Gemini",
    )
    amount: int = Field(default=0, ge=0, le=2**64 - 1)
    destination: str | None = Field(
        default=None,
        description="Base58 pubkey; по умолчанию — pubkey owner из .env",
    )
    intent_id: int | None = Field(
        default=None,
        ge=0,
        le=2**64 - 1,
        description="Если не задан, на chain берётся total_logs + 1",
    )


class VerifyIntentResponse(BaseModel):
    """Ответ Gemini (controlled JSON). Поле риска: `risk_level` 0–100."""

    decision: str
    reasoning: str
    risk_level: int = Field(ge=0, le=100)
    intent_log_signature: str | None = None

    @field_validator("decision")
    @classmethod
    def decision_must_be_enum(cls, v: str) -> str:
        allowed: frozenset[str] = frozenset({"approve", "reject", "escalate"})
        if v not in allowed:
            raise ValueError(f"decision must be one of {sorted(allowed)}")
        return v


class RegisterAgentRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=256)
    max_amount: int = Field(ge=0, le=2**64 - 1)
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Необязательно; при наличии — миссия агента, spawn Eliza, хранение для verify-intent",
    )
    logger_authority: str | None = Field(
        default=None,
        description="Base58 pubkey для поля on-chain; по умолчанию — из KYA_LOGGER_AUTHORITY или signer",
    )

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip() or None


class RegisterAgentResponse(BaseModel):
    agent_id: str
    pda_address: str
    logger_authority: str
    transaction_signature: str
    eliza_status: str | None = Field(
        default=None,
        description="skipped | ok | error",
    )
    eliza_agent_id: str | None = None
    eliza_error: str | None = None


class AgentRecordResponse(BaseModel):
    """Данные on-chain AgentRecord (чтение PDA через anchorpy)."""

    owner: str
    logger_authority: str
    agent_record_address: str
    trust_level: int = Field(ge=0, le=255)
    agent_name: str
    max_amount: int
    total_logs: int
    is_active: bool
    created_at: int
    last_updated: int
    bump: int


class IntentRecordItemResponse(BaseModel):
    intent_id: int
    decision: str
    decision_code: int = Field(ge=0, le=255)
    reasoning: str
    amount: int
    destination: str
    timestamp: int
    intent_record_address: str


class AgentIntentLogsResponse(BaseModel):
    """Последние записи IntentRecord; id перебираются от total_logs вниз (см. heuristic в SolanaService)."""

    owner: str
    agent_record_address: str
    total_logs: int
    logs: list[IntentRecordItemResponse]
