import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from solders.keypair import Keypair

from app.api import endpoints
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.models import VerifyIntentResponse
from app.services.agent_mission_store import clear_all_missions, get_mission
from app.services.eliza_manager import ElizaManager, ElizaSpawnResult
from app.services.gemini import GeminiService


def _settings_no_chain(**kwargs: str | None) -> Settings:
    base = dict(
        gemini_api_key="",
        gemini_model="gemini-2.0-flash",
        solana_rpc_url="https://api.devnet.solana.com",
        solana_private_key="",
        kya_keypair_path=None,
        kya_program_id="",
    )
    base.update({k: v for k, v in kwargs.items() if v is not None})
    return Settings(**base)  # type: ignore[arg-type]


def _settings_chain_stub(**kwargs: object) -> Settings:
    sk = json.dumps(list(bytes(Keypair())))
    base: dict[str, object] = dict(
        gemini_api_key="",
        gemini_model="gemini-2.0-flash",
        solana_rpc_url="https://api.devnet.solana.com",
        solana_private_key=sk,
        kya_keypair_path=None,
        kya_program_id="11111111111111111111111111111111",
        eliza_api_url="http://test-eliza",
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[arg-type]


class StubSolanaRegister:
    """Только register + resolve; без RPC."""

    def resolve_register_logger_authority(self, logger_authority_opt: str | None):
        from solders.pubkey import Pubkey

        if logger_authority_opt and logger_authority_opt.strip():
            return Pubkey.from_string(logger_authority_opt.strip())
        return Pubkey.from_string("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")

    async def register_agent_on_chain(self, **kwargs: object):
        _ = kwargs
        la = self.resolve_register_logger_authority(None)
        return {
            "transaction_signature": "stub_sig",
            "agent_id": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            "pda_address": "stub_pda",
            "logger_authority": str(la),
        }


@pytest.mark.anyio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.anyio
async def test_verify_intent_without_api_key_returns_503():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain(gemini_api_key="")
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/verify-intent",
                json={"intent_text": "hello"},
            )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_verify_intent_with_mock_gemini():
    class StubGemini(GeminiService):
        async def verify_intent(
            self,
            intent_text: str,
            context_json: str | None = None,
            *,
            agent_mission: str | None = None,
        ):
            _ = context_json
            _ = agent_mission
            return VerifyIntentResponse(
                decision="approve",
                reasoning=f"stub:{intent_text[:8]}",
                risk_level=10,
            )

    app.dependency_overrides[get_settings] = lambda: _settings_no_chain(
        gemini_api_key="dummy",
    )
    app.dependency_overrides[endpoints.get_gemini_service] = lambda: StubGemini(
        _settings_no_chain(gemini_api_key="dummy"),
    )

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/verify-intent",
                json={"intent_text": "book a meeting", "context_json": "{}"},
            )
        assert r.status_code == 200
        data = r.json()
        assert data["decision"] == "approve"
        assert data["risk_level"] == 10
        assert data.get("intent_log_signature") is None
        assert "stub:" in data["reasoning"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_register_without_chain_returns_503():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/agents/register",
                json={
                    "agent_name": "test-agent",
                    "max_amount": 1000,
                },
            )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_register_with_chain_stub_no_description_skips_eliza():
    clear_all_missions()
    app.dependency_overrides[get_settings] = lambda: _settings_chain_stub()
    app.dependency_overrides[endpoints.get_solana_service] = lambda: StubSolanaRegister()
    transport = ASGITransport(app=app)
    try:
        with patch.object(
            ElizaManager,
            "spawn_agent_request",
            new_callable=AsyncMock,
        ) as mock_spawn:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.post(
                    "/agents/register",
                    json={"agent_name": "a1", "max_amount": 42},
                )
        assert r.status_code == 200
        data = r.json()
        assert data["eliza_status"] == "skipped"
        assert data["eliza_agent_id"] is None
        assert mock_spawn.await_count == 0
        assert get_mission(data["agent_id"]) is None
    finally:
        app.dependency_overrides.clear()
        clear_all_missions()


@pytest.mark.anyio
async def test_register_with_chain_stub_and_description_calls_eliza():
    clear_all_missions()
    app.dependency_overrides[get_settings] = lambda: _settings_chain_stub()
    app.dependency_overrides[endpoints.get_solana_service] = lambda: StubSolanaRegister()
    transport = ASGITransport(app=app)
    try:
        with patch.object(
            ElizaManager,
            "spawn_agent_request",
            new_callable=AsyncMock,
        ) as mock_spawn:
            mock_spawn.return_value = ElizaSpawnResult(
                ok=True,
                eliza_agent_id="eliza-runtime-1",
                http_status=200,
            )
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.post(
                    "/agents/register",
                    json={
                        "agent_name": "a1",
                        "max_amount": 42,
                        "description": "Only summarize emails",
                    },
                )
        assert r.status_code == 200
        data = r.json()
        assert data["eliza_status"] == "ok"
        assert data["eliza_agent_id"] == "eliza-runtime-1"
        assert data["eliza_error"] is None
        assert mock_spawn.await_count == 1
        assert get_mission(data["agent_id"]) == "Only summarize emails"
    finally:
        app.dependency_overrides.clear()
        clear_all_missions()


@pytest.mark.anyio
async def test_get_agent_logs_invalid_pubkey_returns_400():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain(
        kya_program_id="11111111111111111111111111111111",
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/agents/not-a-pubkey/logs")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_agent_logs_without_program_id_returns_503():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/agents/9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM/logs",
            )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_agent_invalid_pubkey_returns_400():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain(
        kya_program_id="11111111111111111111111111111111",
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/agents/not-a-pubkey")
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_get_agent_without_program_id_returns_503():
    app.dependency_overrides[get_settings] = lambda: _settings_no_chain()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/agents/9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()
