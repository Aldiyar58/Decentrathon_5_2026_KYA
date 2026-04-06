"""anchorpy: программа KYA по IDL `idl/kya_program.json`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anchorpy import Program, Provider, Wallet
from anchorpy_core.idl import Idl
from construct import Container
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import ID as SYS_PROGRAM_ID

from app.core.config import Settings

# Seeds как в IDL (Anchor): agent + owner; log + owner.
SEED_AGENT = b"agent"
SEED_LOG = b"log"


def _load_keypair(settings: Settings) -> Keypair:
    if settings.kya_keypair_path:
        raw = Path(settings.kya_keypair_path).expanduser().read_text(encoding="utf-8")
        secret = json.loads(raw)
    else:
        if not settings.solana_private_key.strip():
            raise ValueError("Задайте SOLANA_PRIVATE_KEY (JSON массив байт) или KYA_KEYPAIR_PATH")
        secret = json.loads(settings.solana_private_key)
    return Keypair.from_bytes(bytes(secret))


def _load_idl(settings: Settings) -> Idl:
    path = Path(settings.kya_idl_path)
    return Idl.from_json(path.read_text(encoding="utf-8"))


def _program_id(settings: Settings) -> Pubkey:
    if not settings.kya_program_id.strip():
        raise ValueError("KYA_PROGRAM_ID не задан")
    return Pubkey.from_string(settings.kya_program_id.strip())


def agent_record_account_key(program: Program) -> str:
    """IDL может называть аккаунт `AgentRecord` или `kya::AgentRecord`."""
    acc = program.account
    if "AgentRecord" in acc:
        return "AgentRecord"
    if "kya::AgentRecord" in acc:
        return "kya::AgentRecord"
    raise ValueError("В IDL нет аккаунта AgentRecord")


def intent_log_account_key(program: Program) -> str:
    acc = program.account
    if "IntentLog" in acc:
        return "IntentLog"
    if "kya::IntentLog" in acc:
        return "kya::IntentLog"
    raise ValueError("В IDL нет аккаунта IntentLog")


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


def _serialize_agent_record(
    data: Container | dict[str, Any],
    agent_pda: Pubkey,
    owner_pk: Pubkey,
) -> dict[str, Any]:
    owner_raw = _container_get(data, "owner")
    if isinstance(owner_raw, Pubkey):
        owner_str = str(owner_raw)
    elif owner_raw is not None:
        try:
            owner_str = str(Pubkey(owner_raw))
        except Exception:
            owner_str = str(owner_raw)
    else:
        owner_str = str(owner_pk)

    tl = _container_get(data, "trust_level", "trustLevel")
    total = _container_get(data, "total_logs", "totalLogs")
    bump = _container_get(data, "bump")
    name = _container_get(data, "agent_name", "agentName") or ""
    max_amt = _container_get(data, "max_amount", "maxAmount")

    return {
        "owner": owner_str,
        "agent_record_address": str(agent_pda),
        "trust_level": int(tl) if tl is not None else 0,
        "agent_name": str(name),
        "max_amount": int(max_amt) if max_amt is not None else 0,
        "total_logs": int(total) if total is not None else 0,
        "bump": int(bump) if bump is not None else 0,
    }


class SolanaService:
    """Ленивая инициализация Program + Provider (подпись транзакций — wallet из .env)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncClient | None = None
        self._provider: Provider | None = None
        self._program: Program | None = None
        self._owner: Keypair | None = None

    async def _ensure_program(self) -> tuple[Program, Keypair]:
        if self._program is not None and self._owner is not None:
            return self._program, self._owner

        self._owner = _load_keypair(self._settings)
        pid = _program_id(self._settings)
        idl = _load_idl(self._settings)

        self._client = AsyncClient(self._settings.solana_rpc_url, Confirmed)
        await self._client.__aenter__()
        wallet = Wallet(self._owner)
        self._provider = Provider(self._client, wallet)
        self._program = Program(idl, pid, self._provider)
        return self._program, self._owner

    def derive_agent_record_pda(self, owner: Pubkey) -> tuple[Pubkey, int]:
        pid = _program_id(self._settings)
        return Pubkey.find_program_address([SEED_AGENT, bytes(owner)], pid)

    def derive_intent_log_pda(self, owner: Pubkey) -> tuple[Pubkey, int]:
        pid = _program_id(self._settings)
        return Pubkey.find_program_address([SEED_LOG, bytes(owner)], pid)

    async def register_agent_on_chain(
        self,
        agent_name: str,
        max_amount: int,
    ) -> dict[str, Any]:
        program, owner = await self._ensure_program()
        owner_pk = owner.pubkey()
        agent_pda, _ = self.derive_agent_record_pda(owner_pk)
        intent_log_pda, _ = self.derive_intent_log_pda(owner_pk)
        sig = await (
            program.methods["register_agent"]
            .args([agent_name, max_amount])
            .accounts(
                {
                    "agent_record": agent_pda,
                    "intent_log": intent_log_pda,
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
            "intent_log_address": str(intent_log_pda),
        }

    async def log_intent_on_chain(
        self,
        intent_id: int,
        decision: str,
        is_approved: bool,
    ) -> str:
        program, owner = await self._ensure_program()
        owner_pk = owner.pubkey()
        agent_pda, _ = self.derive_agent_record_pda(owner_pk)
        intent_log_pda, _ = self.derive_intent_log_pda(owner_pk)
        decision_str = decision[:512] if decision else ""
        sig = await (
            program.methods["log_intent"]
            .args([intent_id, decision_str, is_approved])
            .accounts(
                {
                    "agent_record": agent_pda,
                    "intent_log": intent_log_pda,
                    "owner": owner_pk,
                }
            )
            .rpc()
        )
        return str(sig)

    async def get_agent_info(self) -> dict[str, Any]:
        """AgentRecord для PDA текущего signer; `program.account[…].fetch()` → trust_level и поля."""
        program, owner = await self._ensure_program()
        return await self._fetch_agent_record(program, owner.pubkey())

    @staticmethod
    async def fetch_agent_record_for_owner(
        settings: Settings,
        owner_pubkey: Pubkey,
    ) -> dict[str, Any]:
        """Read-only: AgentRecord по PDA от `owner_pubkey` (без приватного ключа)."""
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
        agent_pda, _ = Pubkey.find_program_address([SEED_AGENT, bytes(owner_pubkey)], pid)
        key = agent_record_account_key(program)
        raw = await program.account[key].fetch(agent_pda)
        return _serialize_agent_record(raw, agent_pda, owner_pubkey)

    @staticmethod
    def _intent_log_pda_for_owner(owner_pubkey: Pubkey, program_id: Pubkey) -> Pubkey:
        pda, _ = Pubkey.find_program_address([SEED_LOG, bytes(owner_pubkey)], program_id)
        return pda

    @staticmethod
    def _serialize_intent_entry(entry: Any) -> dict[str, Any]:
        if isinstance(entry, dict):
            iid = entry.get("intent_id", entry.get("intentId"))
            dec = entry.get("decision", "")
            appr = entry.get("is_approved", entry.get("isApproved"))
            ts = entry.get("timestamp", entry.get("ts"))
        else:
            iid = _container_get(entry, "intent_id", "intentId")
            dec = _container_get(entry, "decision") or ""
            appr = _container_get(entry, "is_approved", "isApproved")
            ts = _container_get(entry, "timestamp")
        return {
            "intent_id": int(iid) if iid is not None else 0,
            "decision": str(dec),
            "is_approved": bool(appr) if appr is not None else False,
            "timestamp": int(ts) if ts is not None else 0,
        }

    @staticmethod
    async def fetch_intent_log_for_owner(
        settings: Settings,
        owner_pubkey: Pubkey,
    ) -> dict[str, Any]:
        if not settings.kya_program_id.strip():
            raise ValueError("KYA_PROGRAM_ID не задан")
        idl = _load_idl(settings)
        pid = _program_id(settings)
        log_pda = SolanaService._intent_log_pda_for_owner(owner_pubkey, pid)
        conn = AsyncClient(settings.solana_rpc_url, Confirmed)
        await conn.__aenter__()
        try:
            prov = Provider(conn, Wallet.dummy())
            program = Program(idl, pid, prov)
            acc_key = intent_log_account_key(program)
            raw = await program.account[acc_key].fetch(log_pda)
            logs_raw = _container_get(raw, "logs")
            if logs_raw is None and hasattr(raw, "logs"):
                logs_raw = raw.logs
            entries: list[dict[str, Any]] = []
            if logs_raw is not None:
                for item in logs_raw:
                    entries.append(SolanaService._serialize_intent_entry(item))
            return {
                "owner": str(owner_pubkey),
                "intent_log_address": str(log_pda),
                "logs": entries,
            }
        finally:
            await conn.__aexit__(None, None, None)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
        self._provider = None
        self._program = None
        self._owner = None


def is_chain_configured(settings: Settings) -> bool:
    return bool(settings.kya_program_id.strip()) and (
        bool(settings.solana_private_key.strip()) or bool(settings.kya_keypair_path)
    )


def is_program_id_configured(settings: Settings) -> bool:
    return bool(settings.kya_program_id.strip())
