"""Google Gemini (google-genai): анализ интента с controlled JSON."""

from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from app.core.config import Settings
from app.schemas.models import VerifyIntentResponse

logger = logging.getLogger(__name__)

KYA_SYSTEM_INSTRUCTION = """You are KYA (Know Your Agent), a compliance-oriented intent analyzer for autonomous agents.

Your task:
- Read the user's message and any optional structured context.
- Decide whether the described intent is acceptable under a cautious default policy (no harm, no illegal or clearly abusive goals, no credential theft or deception).
- Output ONLY a JSON object that conforms to the enforced response schema. Do not use markdown fences or prose outside JSON.

Field semantics:
- decision: "approve" if the intent is clearly acceptable; "reject" if clearly unacceptable; "escalate" if uncertain or needs human review.
- reasoning: concise justification referencing the main factors you weighed.
- risk_level: integer from 0 to 100 quantifying policy and safety risk (0 = routine/low concern; ~50 = sensitive or ambiguous; 80+ = harmful, disallowed, or high-stakes; use the full range consistently).

If context is missing, infer conservatively, prefer "escalate" over "approve" when unsure, and assign a higher risk_level when uncertain.
"""

MISSION_ALIGNMENT_BLOCK = """

## Mission alignment (when a registered mission is provided below)

Compare the agent's current intent to its registered mission.
- If the described action falls outside the mission, contradicts it, or is not a reasonable way to fulfill it, you MUST respond with decision "reject" (on-chain this is decision code 1).
- If the intent is within mission scope, still apply the usual safety and policy rules from the base instructions above.
- If mission alignment is ambiguous, use "escalate" rather than "approve".

Registered agent mission:
---
{mission}
---
"""


def _system_instruction(agent_mission: str | None) -> str:
    base = KYA_SYSTEM_INSTRUCTION
    if agent_mission and agent_mission.strip():
        return base + MISSION_ALIGNMENT_BLOCK.format(mission=agent_mission.strip())
    return base


VERIFY_INTENT_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "decision": types.Schema(
            type=types.Type.STRING,
            enum=["approve", "reject", "escalate"],
        ),
        "reasoning": types.Schema(type=types.Type.STRING),
        "risk_level": types.Schema(
            type=types.Type.INTEGER,
            minimum=0,
            maximum=100,
        ),
    },
    required=["decision", "reasoning", "risk_level"],
)

_clients: dict[str, genai.Client] = {}


def _client_for(api_key: str) -> genai.Client:
    if not api_key.strip():
        raise ValueError("GEMINI_API_KEY is empty")
    if api_key not in _clients:
        _clients[api_key] = genai.Client(api_key=api_key)
    return _clients[api_key]


class GeminiService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _user_content(self, intent_text: str, context_json: str | None) -> str:
        parts = [f"Intent text:\n{intent_text}"]
        if context_json is not None and context_json.strip():
            parts.append(f"Context (JSON):\n{context_json}")
        return "\n\n".join(parts)

    def _parse_response_payload(self, response: Any) -> VerifyIntentResponse:
        if getattr(response, "parsed", None) is not None:
            parsed = response.parsed
            if isinstance(parsed, dict):
                return VerifyIntentResponse.model_validate(parsed)
            if isinstance(parsed, VerifyIntentResponse):
                return parsed
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Empty response from Gemini")
        return VerifyIntentResponse.model_validate_json(text)

    async def verify_intent(
        self,
        intent_text: str,
        context_json: str | None = None,
        *,
        agent_mission: str | None = None,
    ) -> VerifyIntentResponse:
        client = _client_for(self._settings.gemini_api_key)
        config = types.GenerateContentConfig(
            system_instruction=_system_instruction(agent_mission),
            response_mime_type="application/json",
            response_schema=VERIFY_INTENT_RESPONSE_SCHEMA,
        )
        try:
            resp = await client.aio.models.generate_content(
                model=self._settings.gemini_model,
                contents=self._user_content(intent_text, context_json),
                config=config,
            )
        except Exception as e:
            logger.exception("Gemini generate_content failed")
            raise RuntimeError(f"Gemini API error: {e}") from e

        try:
            return self._parse_response_payload(resp)
        except Exception as e:
            logger.warning("Gemini response parse failed: %s; raw=%s", e, getattr(resp, "text", None))
            raise ValueError(f"Invalid Gemini JSON payload: {e}") from e
