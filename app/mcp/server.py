"""
MCP-сервер KYA (stdio). Инструменты: verify_intent, get_credential, register_agent.

Запуск из каталога kya-backend:
    python -m app.mcp.server
"""

from __future__ import annotations

import json
import logging
import secrets

from mcp.server.fastmcp import FastMCP
from solders.pubkey import Pubkey

from app.core.config import get_settings
from app.services.gemini import GeminiService
from app.services.solana import (
    SolanaService,
    is_chain_configured,
    is_program_id_configured,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "KYA",
    instructions="KYA (Know Your Agent): проверка интентов через Gemini и учёт на Solana.",
)


@mcp.tool(
    name="verify_intent",
    description="Анализ интента через Gemini; при настроенном chain — logIntent на Solana.",
)
async def verify_intent(
    intent_text: str,
    context_json: str | None = None,
    record_on_chain: bool = True,
) -> str:
    settings = get_settings()
    if not settings.gemini_api_key.strip():
        return json.dumps({"error": "GEMINI_API_KEY не задан"})

    gemini = GeminiService(settings)
    try:
        result = await gemini.verify_intent(intent_text, context_json)
    except Exception as e:
        return json.dumps({"error": str(e)})

    out = result.model_dump()
    if record_on_chain and is_chain_configured(settings):
        sol = SolanaService(settings)
        try:
            sig = await sol.log_intent_on_chain(
                intent_id=secrets.randbelow(2**64),
                decision=result.decision,
                is_approved=result.decision == "approve",
            )
            out["intent_log_signature"] = sig
        except Exception as e:
            logger.warning("MCP log_intent_on_chain: %s", e, exc_info=True)
            out["intent_log_signature"] = None
    else:
        out["intent_log_signature"] = None

    return json.dumps(out, ensure_ascii=False)


@mcp.tool(
    name="get_credential",
    description="Данные AgentRecord (trust_level и др.) по owner pubkey (base58).",
)
async def get_credential(owner_pubkey: str) -> str:
    settings = get_settings()
    if not is_program_id_configured(settings):
        return json.dumps({"error": "KYA_PROGRAM_ID не задан"})
    try:
        pk = Pubkey.from_string(owner_pubkey.strip())
    except Exception as e:
        return json.dumps({"error": f"Некорректный pubkey: {e}"})
    try:
        data = await SolanaService.fetch_agent_record_for_owner(settings, pk)
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps(data, ensure_ascii=False)


@mcp.tool(
    name="register_agent",
    description="Первичная регистрация агента on-chain (registerAgent), подпись из .env.",
)
async def register_agent() -> str:
    settings = get_settings()
    if not is_chain_configured(settings):
        return json.dumps(
            {"error": "Нужны KYA_PROGRAM_ID и SOLANA_PRIVATE_KEY (или KYA_KEYPAIR_PATH)"}
        )
    sol = SolanaService(settings)
    try:
        sig = await sol.register_agent_on_chain()
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"transaction_signature": sig}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
