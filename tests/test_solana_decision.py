from app.services.solana import (
    DECISION_APPROVE_U8,
    DECISION_ESCALATE_U8,
    DECISION_REJECT_U8,
    decision_u8_to_label,
    gemini_decision_to_u8,
)


def test_gemini_decision_to_u8_mapping():
    assert gemini_decision_to_u8("approve") == DECISION_APPROVE_U8
    assert gemini_decision_to_u8("reject") == DECISION_REJECT_U8
    assert gemini_decision_to_u8("escalate") == DECISION_ESCALATE_U8
    assert gemini_decision_to_u8("unknown") == DECISION_ESCALATE_U8


def test_decision_u8_to_label_roundtrip():
    for s in ("approve", "reject", "escalate"):
        assert decision_u8_to_label(gemini_decision_to_u8(s)) == s
