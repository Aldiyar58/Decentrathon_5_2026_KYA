import logging
import secrets

from anchorpy.error import AccountDoesNotExistError
from fastapi import APIRouter, Depends, HTTPException, status
from solders.pubkey import Pubkey

from app.core.config import Settings, get_settings
from app.core.deps import get_gemini_service, get_solana_service
from app.schemas.models import AgentRecordResponse, VerifyIntentRequest, VerifyIntentResponse
from app.services.gemini import GeminiService
from app.services.solana import (
    SolanaService,
    is_chain_configured,
    is_program_id_configured,
)

router = APIRouter(tags=["kya"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "kya-api"}


@router.post("/verify-intent", response_model=VerifyIntentResponse)
async def verify_intent(
    body: VerifyIntentRequest,
    settings: Settings = Depends(get_settings),
    gemini: GeminiService = Depends(get_gemini_service),
    solana: SolanaService = Depends(get_solana_service),
):
    if not settings.gemini_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured",
        )
    try:
        result = await gemini.verify_intent(body.intent_text, body.context_json)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    payload = result.model_dump()
    if is_chain_configured(settings):
        intent_id = secrets.randbelow(2**64)
        is_approved = result.decision == "approve"
        try:
            sig = await solana.log_intent_on_chain(
                intent_id=intent_id,
                decision=result.decision,
                is_approved=is_approved,
            )
            payload["intent_log_signature"] = sig
        except Exception as e:
            logger.warning("log_intent_on_chain failed: %s", e, exc_info=True)
            payload["intent_log_signature"] = None
    else:
        payload["intent_log_signature"] = None

    return VerifyIntentResponse.model_validate(payload)


@router.get("/agents/{agent_id}", response_model=AgentRecordResponse)
async def get_agent(
    agent_id: str,
    settings: Settings = Depends(get_settings),
):
    """`agent_id` — base58 **owner** (кошелёк), от которого считается PDA AgentRecord."""
    if not is_program_id_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KYA_PROGRAM_ID обязателен для чтения из chain",
        )
    try:
        owner_pk = Pubkey.from_string(agent_id.strip())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректный agent_id (ожидается pubkey owner в base58): {e}",
        ) from e
    try:
        data = await SolanaService.fetch_agent_record_for_owner(settings, owner_pk)
    except AccountDoesNotExistError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AgentRecord не найден для данного owner",
        ) from None
    except Exception as e:
        logger.exception("fetch_agent_record_for_owner failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    return AgentRecordResponse.model_validate(data)


@router.post("/agents/register")
async def register_agent(
    settings: Settings = Depends(get_settings),
    solana: SolanaService = Depends(get_solana_service),
):
    if not is_chain_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KYA_PROGRAM_ID и ключ (SOLANA_PRIVATE_KEY / KYA_KEYPAIR_PATH) обязательны",
        )
    try:
        sig = await solana.register_agent_on_chain()
    except Exception as e:
        logger.exception("register_agent_on_chain failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    return {"transaction_signature": sig}
