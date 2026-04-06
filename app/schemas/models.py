from pydantic import BaseModel, Field, field_validator


class VerifyIntentRequest(BaseModel):
    intent_text: str = Field(min_length=1)
    context_json: str | None = None


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


class RegisterAgentResponse(BaseModel):
    agent_id: str
    pda_address: str
    intent_log_address: str
    transaction_signature: str


class AgentRecordResponse(BaseModel):
    """Данные on-chain AgentRecord (чтение PDA через anchorpy)."""

    owner: str
    agent_record_address: str
    trust_level: int
    agent_name: str
    max_amount: int
    total_logs: int
    bump: int


class IntentEntryResponse(BaseModel):
    intent_id: int
    decision: str
    is_approved: bool
    timestamp: int


class IntentLogResponse(BaseModel):
    owner: str
    intent_log_address: str
    logs: list[IntentEntryResponse]
