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


class AgentRecordResponse(BaseModel):
    """Данные on-chain AgentRecord (read-only по owner pubkey)."""

    owner: str
    agent_record_address: str
    trust_level: int
    total_logs: int
    version: int
    bump: int
