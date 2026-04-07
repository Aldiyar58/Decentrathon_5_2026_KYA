import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    yield
    get_settings.cache_clear()


@pytest.mark.anyio
async def test_mcp_sse_rejects_when_no_keys_configured():
    os.environ.pop("KYA_MCP_API_KEYS", None)
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/mcp/sse")
    assert r.status_code == 401


@pytest.mark.anyio
async def test_mcp_sse_rejects_missing_x_api_key():
    os.environ["KYA_MCP_API_KEYS"] = "secret-one"
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/mcp/sse")
        assert r.status_code == 401
    finally:
        os.environ.pop("KYA_MCP_API_KEYS", None)
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_mcp_sse_rejects_wrong_x_api_key():
    os.environ["KYA_MCP_API_KEYS"] = "secret-one"
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/mcp/sse", headers={"X-API-KEY": "wrong"})
        assert r.status_code == 401
    finally:
        os.environ.pop("KYA_MCP_API_KEYS", None)
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_mcp_messages_rejects_without_key():
    os.environ["KYA_MCP_API_KEYS"] = "k"
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/mcp/messages/?session_id=00000000000000000000000000000000",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Content-Type": "application/json"},
            )
        assert r.status_code == 401
    finally:
        os.environ.pop("KYA_MCP_API_KEYS", None)
        get_settings.cache_clear()


@pytest.mark.anyio
async def test_mcp_messages_with_valid_key_unknown_session_returns_404():
    os.environ["KYA_MCP_API_KEYS"] = "good-key"
    get_settings.cache_clear()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sid = uuid.uuid4().hex
            r = await client.post(
                f"/mcp/messages/?session_id={sid}",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={
                    "Content-Type": "application/json",
                    "X-API-KEY": "good-key",
                },
            )
        assert r.status_code == 404
    finally:
        os.environ.pop("KYA_MCP_API_KEYS", None)
        get_settings.cache_clear()
