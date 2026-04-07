"""Общая логика MCP tools (stdio и HTTP/SSE)."""

from __future__ import annotations

import json
import logging
from typing import Any

from anchorpy.error import AccountDoesNotExistError
from solders.pubkey import Pubkey

from app.core.config import Settings
from app.services.agent_mission_store import get_mission, set_mission
from app.services.eliza_manager import ElizaManager
from app.services.gemini import GeminiService
from app.services.solana import (
    SolanaService,
    gemini_decision_to_u8,
    is_chain_configured,
    is_program_id_configured,
)

logger = logging.getLogger(__name__)


async def verify_intent_handler(
    settings: Settings,
    intent_text: str,
    context_json: str | None = None,
    record_on_chain: bool = True,
    amount: int = 0,
    destination: str | None = None,
    agent_id: str | None = None,
) -> str:
    if not settings.gemini_api_key.strip():
        return json.dumps({"error": "GEMINI_API_KEY не задан"})

    gemini = GeminiService(settings)
    mission = (
        get_mission(agent_id.strip())
        if agent_id and agent_id.strip()
        else None
    )
    try:
        result = await gemini.verify_intent(
            intent_text,
            context_json,
            agent_mission=mission,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

    out = result.model_dump()
    if record_on_chain and is_chain_configured(settings):
        dest: Pubkey | None = None
        if destination and destination.strip():
            try:
                dest = Pubkey.from_string(destination.strip())
            except Exception as e:
                return json.dumps({"error": f"Некорректный destination: {e}"})
        sol = SolanaService(settings)
        try:
            sig = await sol.log_intent_on_chain(
                intent_id=None,
                decision_u8=gemini_decision_to_u8(result.decision),
                reasoning=result.reasoning,
                amount=amount,
                destination=dest,
            )
            out["intent_log_signature"] = sig
        except Exception as e:
            logger.warning("MCP log_intent_on_chain: %s", e, exc_info=True)
            out["intent_log_signature"] = None
    else:
        out["intent_log_signature"] = None

    return json.dumps(out, ensure_ascii=False)


async def execute_register_agent_flow(
    settings: Settings,
    sol: SolanaService,
    *,
    agent_name: str,
    max_amount: int,
    logger_authority: str | None,
    description: str | None,
) -> dict[str, Any]:
    logger_pk = sol.resolve_register_logger_authority(logger_authority)
    out = await sol.register_agent_on_chain(
        agent_name=agent_name,
        max_amount=max_amount,
        logger_authority=logger_pk,
    )
    agent_id = out["agent_id"]
    desc = description.strip() if description and description.strip() else None
    if desc:
        set_mission(agent_id, desc)
        em = ElizaManager(settings)
        spawn = await em.spawn_agent_request(agent_name, desc, agent_id)
        if spawn.ok:
            out["eliza_status"] = "ok"
            out["eliza_agent_id"] = spawn.eliza_agent_id
            out["eliza_error"] = None
        else:
            out["eliza_status"] = "error"
            out["eliza_agent_id"] = None
            out["eliza_error"] = spawn.error or "Eliza spawn failed"
    else:
        out["eliza_status"] = "skipped"
        out["eliza_agent_id"] = None
        out["eliza_error"] = None
    return out


async def register_agent_handler(
    settings: Settings,
    agent_name: str,
    max_amount: int,
    logger_authority: str | None = None,
    description: str | None = None,
) -> str:
    if not is_chain_configured(settings):
        return json.dumps(
            {"error": "Нужны KYA_PROGRAM_ID и SOLANA_PRIVATE_KEY (или KYA_KEYPAIR_PATH)"}
        )
    sol = SolanaService(settings)
    try:
        out = await execute_register_agent_flow(
            settings,
            sol,
            agent_name=agent_name,
            max_amount=max_amount,
            logger_authority=logger_authority,
            description=description,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps(out, ensure_ascii=False)


async def get_credential_handler(settings: Settings, owner_pubkey: str) -> str:
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


async def get_agent_info_handler(settings: Settings) -> str:
    if not is_chain_configured(settings):
        return json.dumps(
            {"error": "Нужны KYA_PROGRAM_ID и SOLANA_PRIVATE_KEY (или KYA_KEYPAIR_PATH)"}
        )
    sol = SolanaService(settings)
    try:
        data = await sol.get_agent_info()
    except AccountDoesNotExistError:
        return json.dumps({"error": "AgentRecord не найден для кошелька сервера (owner)"})
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps(data, ensure_ascii=False)
