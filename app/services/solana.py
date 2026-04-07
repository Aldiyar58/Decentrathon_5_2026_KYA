"""anchorpy: KYA по legacy IDL `idl/kya_program.json`.

Логи: отдельный аккаунт IntentRecord на интент; PDA [b\"intent\", agent_pda, intent_id u64 LE].
Решение на chain — u8: 0=Approve, 1=Reject, 2=Escalate (таблица в memory-bank/progress.md).
log_intent подписывает logger_authority (см. Settings KYA_LOGGER_*).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anchorpy import Program, Provider, Wallet
from anchorpy.error import AccountDoesNotExistError
from anchorpy_core.idl import Idl
from construct import Container
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID

from app.core.config import Settings

SEED_AGENT = b"agent"
SEED_INTENT = b"intent"

# On-chain enum: 0=Approve, 1=Reject, 2=Escalate (как в ТЗ).
DECISION_APPROVE_U8 = 0
DECISION_REJECT_U8 = 1
DECISION_ESCALATE_U8 = 2


def gemini_decision_to_u8(decision: str) -> int:
    """Строка от Gemini -> u8 для инструкции log_intent: approve->0, reject->1, escalate->2."""
    return {
        "approve": DECISION_APPROVE_U8,
        "reject": DECISION_REJECT_U8,
        "escalate": DECISION_ESCALATE_U8,
    }.get(decision, DECISION_ESCALATE_U8)


def decision_u8_to_label(code: int) -> str:
    """Обратное отображение u8 -> метка API (0/1/2 иначе unknown)."""
    return {
        DECISION_APPROVE_U8: "approve",
        DECISION_REJECT_U8: "reject",
        DECISION_ESCALATE_U8: "escalate",
    }.get(int(code), "unknown")


def _load_keypair(settings: Settings) -> Keypair:
    if settings.kya_keypair_path:
        raw = Path(settings.kya_keypair_path).expanduser().read_text(encoding="utf-8")
        secret = json.loads(raw)
    else:
        if not settings.solana_private_key.strip():
            raise ValueError("Задайте SOLANA_PRIVATE_KEY (JSON массив байт) или KYA_KEYPAIR_PATH")
        secret = json.loads(settings.solana_private_key)
    return Keypair.from_bytes(bytes(secret))


def _load_logger_keypair(settings: Settings) -> Keypair:
    if settings.kya_logger_keypair_path:
        raw = Path(settings.kya_logger_keypair_path).expanduser().read_text(encoding="utf-8")
        secret = json.loads(raw)
        return Keypair.from_bytes(bytes(secret))
    if settings.kya_logger_private_key.strip():
        secret = json.loads(settings.kya_logger_private_key)
        return Keypair.from_bytes(bytes(secret))
    return _load_keypair(settings)


def resolve_logger_authority_pubkey(settings: Settings, owner_kp: Keypair, override: Pubkey | None) -> Pubkey:
    if override is not None:
        return override
    if settings.kya_logger_authority.strip():
        return Pubkey.from_string(settings.kya_logger_authority.strip())
    return _load_logger_keypair(settings).pubkey()


def _load_idl(settings: Settings) -> Idl:
    path = Path(settings.kya_idl_path)
    return Idl.from_json(path.read_text(encoding="utf-8"))


def _program_id(settings: Settings) -> Pubkey:
    if not settings.kya_program_id.strip():
        raise ValueError("KYA_PROGRAM_ID не задан")
    return Pubkey.from_string(settings.kya_program_id.strip())


def agent_record_account_key(program: Program) -> str:
    acc = program.account
    if "AgentRecord" in acc:
        return "AgentRecord"
    if "kya::AgentRecord" in acc:
        return "kya::AgentRecord"
    raise ValueError("В IDL нет аккаунта AgentRecord")


def intent_record_account_key(program: Program) -> str:
    acc = program.account
    if "IntentRecord" in acc:
        return "IntentRecord"
    if "kya::IntentRecord" in acc:
        return "kya::IntentRecord"
    raise ValueError("В IDL нет аккаунта IntentRecord")


def derive_agent_record_pda(owner: Pubkey, program_id: Pubkey) -> tuple[Pubkey, int]:
    return Pubkey.find_program_address([SEED_AGENT, bytes(owner)], program_id)


def derive_intent_record_pda(agent_record_pda: Pubkey, intent_id: int, program_id: Pubkey) -> tuple[Pubkey, int]:
    seed_id = int(intent_id).to_bytes(8, "little", signed=False)
    return Pubkey.find_program_address([SEED_INTENT, bytes(agent_record_pda), seed_id], program_id)


def _container_get(data: Container | dict[str, Any], *names: str) -> Any:
    for name in names:
        if isinstance(data, dict):
            if name in data:
                return data[name]
        else:
            if hasattr(data, name):
                return getattr(data, name)
            if name in data:
                return data[name]
    return None


def _as_pubkey_str(raw: Any) -> str:
    if isinstance(raw, Pubkey):
        return str(raw)
    if raw is None:
        return ""
    try:
        return str(Pubkey(raw))
    except Exception:
        return str(raw)


def _serialize_agent_record(
    data: Container | dict[str, Any],
    agent_pda: Pubkey,
    owner_pk: Pubkey,
) -> dict[str, Any]:
    owner_raw = _container_get(data, "owner")
    owner_str = _as_pubkey_str(owner_raw) if owner_raw is not None else str(owner_pk)

    logger_raw = _container_get(data, "logger_authority", "loggerAuthority")
    logger_str = _as_pubkey_str(logger_raw)

    tl = _container_get(data, "trust_level", "trustLevel")
    total = _container_get(data, "total_logs", "totalLogs")
    bump = _container_get(data, "bump")
    name = _container_get(data, "agent_name", "agentName") or ""
    max_amt = _container_get(data, "max_amount", "maxAmount")
    active = _container_get(data, "is_active", "isActive")
    created = _container_get(data, "created_at", "createdAt")
    updated = _container_get(data, "last_updated", "lastUpdated")

    return {
        "owner": owner_str,
        "logger_authority": logger_str,
        "agent_record_address": str(agent_pda),
        "trust_level": int(tl) if tl is not None else 0,
        "agent_name": str(name),
        "max_amount": int(max_amt) if max_amt is not None else 0,
        "total_logs": int(total) if total is not None else 0,
        "is_active": bool(active) if active is not None else False,
        "created_at": int(created) if created is not None else 0,
        "last_updated": int(updated) if updated is not None else 0,
        "bump": int(bump) if bump is not None else 0,
    }


def _serialize_intent_record(data: Container | dict[str, Any], record_pda: Pubkey) -> dict[str, Any]:
    iid = _container_get(data, "intent_id", "intentId")
    dec = _container_get(data, "decision")
    reasoning = _container_get(data, "reasoning") or ""
    amount = _container_get(data, "amount")
    dest = _container_get(data, "destination")
    ts = _container_get(data, "timestamp")
    code = int(dec) if dec is not None else 0
    return {
        "intent_id": int(iid) if iid is not None else 0,
        "decision": decision_u8_to_label(code),
        "decision_code": code,
        "reasoning": str(reasoning),
        "amount": int(amount) if amount is not None else 0,
        "destination": _as_pubkey_str(dest),
        "timestamp": int(ts) if ts is not None else 0,
        "intent_record_address": str(record_pda),
    }


class SolanaService:
    """RPC + anchorpy; owner подписывает register, logger_authority — log_intent (часто тот же ключ)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncClient | None = None
        self._idl: Idl | None = None
        self._pid: Pubkey | None = None

    def _idl_pid(self) -> tuple[Idl, Pubkey]:
        if self._idl is None or self._pid is None:
            self._idl = _load_idl(self._settings)
            self._pid = _program_id(self._settings)
        return self._idl, self._pid

    async def _ensure_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(self._settings.solana_rpc_url, Confirmed)
            await self._client.__aenter__()
        return self._client

    async def _program_with_wallet(self, wallet_kp: Keypair) -> Program:
        client = await self._ensure_client()
        idl, pid = self._idl_pid()
        return Program(idl, pid, Provider(client, Wallet(wallet_kp)))

    def resolve_register_logger_authority(self, logger_authority_opt: str | None) -> Pubkey:
        owner_kp = _load_keypair(self._settings)
        override = (
            Pubkey.from_string(logger_authority_opt.strip())
            if logger_authority_opt and logger_authority_opt.strip()
            else None
        )
        return resolve_logger_authority_pubkey(self._settings, owner_kp, override)

    async def register_agent_on_chain(
        self,
        agent_name: str,
        max_amount: int,
        logger_authority: Pubkey,
    ) -> dict[str, Any]:
        owner_kp = _load_keypair(self._settings)
        program = await self._program_with_wallet(owner_kp)
        owner_pk = owner_kp.pubkey()
        agent_pda, _ = derive_agent_record_pda(owner_pk, program.program_id)
        sig = await (
            program.methods["register_agent"]
            .args([agent_name, max_amount, logger_authority])
            .accounts(
                {
                    "agent_record": agent_pda,
                    "owner": owner_pk,
                    "system_program": SYS_PROGRAM_ID,
                }
            )
            .rpc()
        )
        return {
            "transaction_signature": str(sig),
            "agent_id": str(owner_pk),
            "pda_address": str(agent_pda),
            "logger_authority": str(logger_authority),
        }

    async def log_intent_on_chain(
        self,
        *,
        intent_id: int | None,
        decision_u8: int,
        reasoning: str,
        amount: int,
        destination: Pubkey | None = None,
    ) -> str:
        owner_kp = _load_keypair(self._settings)
        logger_kp = _load_logger_keypair(self._settings)
        owner_pk = owner_kp.pubkey()
        idl, pid = self._idl_pid()
        agent_pda, _ = derive_agent_record_pda(owner_pk, pid)
        dest = destination if destination is not None else owner_pk

        program = await self._program_with_wallet(logger_kp)
        if intent_id is None:
            summary = await SolanaService._fetch_agent_record(program, owner_pk)
            next_id = int(summary["total_logs"]) + 1
        else:
            next_id = int(intent_id)

        intent_rec_pda, _ = derive_intent_record_pda(agent_pda, next_id, pid)
        reasoning_trim = reasoning[:2048] if reasoning else ""

        sig = await (
            program.methods["log_intent"]
            .args([next_id, decision_u8, reasoning_trim, amount, dest])
            .accounts(
                {
                    "agent_record": agent_pda,
                    "intent_record": intent_rec_pda,
                    "owner": owner_pk,
                    "logger_authority": logger_kp.pubkey(),
                    "system_program": SYS_PROGRAM_ID,
                }
            )
            .rpc()
        )
        return str(sig)

    async def get_agent_info(self) -> dict[str, Any]:
        owner_kp = _load_keypair(self._settings)
        program = await self._program_with_wallet(owner_kp)
        return await SolanaService._fetch_agent_record(program, owner_kp.pubkey())

    @staticmethod
    async def fetch_agent_record_for_owner(
        settings: Settings,
        owner_pubkey: Pubkey,
    ) -> dict[str, Any]:
        if not settings.kya_program_id.strip():
            raise ValueError("KYA_PROGRAM_ID не задан")
        idl = _load_idl(settings)
        pid = _program_id(settings)
        conn = AsyncClient(settings.solana_rpc_url, Confirmed)
        await conn.__aenter__()
        try:
            prov = Provider(conn, Wallet.dummy())
            program = Program(idl, pid, prov)
            return await SolanaService._fetch_agent_record(program, owner_pubkey)
        finally:
            await conn.__aexit__(None, None, None)

    @staticmethod
    async def _fetch_agent_record(program: Program, owner_pubkey: Pubkey) -> dict[str, Any]:
        pid = program.program_id
        agent_pda, _ = derive_agent_record_pda(owner_pubkey, pid)
        key = agent_record_account_key(program)
        raw = await program.account[key].fetch(agent_pda)
        return _serialize_agent_record(raw, agent_pda, owner_pubkey)

    @staticmethod
    async def fetch_recent_intent_logs_for_owner(
        settings: Settings,
        owner_pubkey: Pubkey,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Эвристика: intent_id считаются 1..total_logs (если на chain другая схема — часть слотов будет пропущена)."""
        if not settings.kya_program_id.strip():
            raise ValueError("KYA_PROGRAM_ID не задан")
        idl = _load_idl(settings)
        pid = _program_id(settings)
        conn = AsyncClient(settings.solana_rpc_url, Confirmed)
        await conn.__aenter__()
        try:
            prov = Provider(conn, Wallet.dummy())
            program = Program(idl, pid, prov)
            agent = await SolanaService._fetch_agent_record(program, owner_pubkey)
            n = int(agent["total_logs"])
            agent_pda = Pubkey.from_string(agent["agent_record_address"])
            acc_key = intent_record_account_key(program)
            logs: list[dict[str, Any]] = []
            if n <= 0:
                return {
                    "owner": str(owner_pubkey),
                    "agent_record_address": str(agent_pda),
                    "total_logs": n,
                    "logs": logs,
                }
            probe = min(limit, n)
            for k in range(probe):
                i = n - k
                rec_pda, _ = derive_intent_record_pda(agent_pda, i, pid)
                try:
                    raw = await program.account[acc_key].fetch(rec_pda)
                    logs.append(_serialize_intent_record(raw, rec_pda))
                except AccountDoesNotExistError:
                    continue
            return {
                "owner": str(owner_pubkey),
                "agent_record_address": str(agent_pda),
                "total_logs": n,
                "logs": logs,
            }
        finally:
            await conn.__aexit__(None, None, None)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
        self._idl = None
        self._pid = None


def is_chain_configured(settings: Settings) -> bool:
    return bool(settings.kya_program_id.strip()) and (
        bool(settings.solana_private_key.strip()) or bool(settings.kya_keypair_path)
    )


def is_program_id_configured(settings: Settings) -> bool:
    return bool(settings.kya_program_id.strip())
