import logging

from anchorpy.error import AccountDoesNotExistError
from fastapi import APIRouter, Depends, HTTPException, status
from solders.pubkey import Pubkey

from app.core.config import Settings, get_settings
from app.core.deps import get_gemini_service, get_solana_service
from app.schemas.models import (
    AgentIntentLogsResponse,
    AgentRecordResponse,
    RegisterAgentRequest,
    RegisterAgentResponse,
    VerifyIntentRequest,
    VerifyIntentResponse,
)
from app.services.agent_mission_store import get_mission
from app.services.gemini import GeminiService
from app.services.mcp_tool_handlers import execute_register_agent_flow
from app.services.solana import (
    SolanaService,
    gemini_decision_to_u8,
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
    mission = (
        get_mission(body.agent_id.strip())
        if body.agent_id and body.agent_id.strip()
        else None
    )
    try:
        result = await gemini.verify_intent(
            body.intent_text,
            body.context_json,
            agent_mission=mission,
        )
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
        dest: Pubkey | None = None
        if body.destination and body.destination.strip():
            try:
                dest = Pubkey.from_string(body.destination.strip())
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Некорректный destination (base58): {e}",
                ) from e
        try:
            sig = await solana.log_intent_on_chain(
                intent_id=body.intent_id,
                decision_u8=gemini_decision_to_u8(result.decision),
                reasoning=result.reasoning,
                amount=body.amount,
                destination=dest,
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


@router.get("/agents/{agent_id}/logs", response_model=AgentIntentLogsResponse)
async def get_agent_logs(
    agent_id: str,
    settings: Settings = Depends(get_settings),
):
    """Чтение последних IntentRecord: id от `total_logs` вниз (эвристика 1..total_logs)."""
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
        data = await SolanaService.fetch_recent_intent_logs_for_owner(
            settings,
            owner_pk,
            limit=20,
        )
    except AccountDoesNotExistError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AgentRecord не найден для данного owner",
        ) from None
    except Exception as e:
        logger.exception("fetch_recent_intent_logs_for_owner failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    return AgentIntentLogsResponse.model_validate(data)


@router.post("/agents/register", response_model=RegisterAgentResponse)
async def register_agent(
    body: RegisterAgentRequest,
    settings: Settings = Depends(get_settings),
    solana: SolanaService = Depends(get_solana_service),
):
    if not is_chain_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KYA_PROGRAM_ID и ключ (SOLANA_PRIVATE_KEY / KYA_KEYPAIR_PATH) обязательны",
        )
    try:
        out = await execute_register_agent_flow(
            settings,
            solana,
            agent_name=body.agent_name,
            max_amount=body.max_amount,
            logger_authority=body.logger_authority,
            description=body.description,
        )
    except Exception as e:
        logger.exception("register_agent flow failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    return RegisterAgentResponse(
        agent_id=out["agent_id"],
        pda_address=out["pda_address"],
        logger_authority=out["logger_authority"],
        transaction_signature=out["transaction_signature"],
        eliza_status=out.get("eliza_status"),
        eliza_agent_id=out.get("eliza_agent_id"),
        eliza_error=out.get("eliza_error"),
    )
