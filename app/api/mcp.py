"""
MCP поверх HTTP: SSE + POST messages (SseServerTransport).

Клиенты: GET /mcp/sse (EventSource), затем POST JSON-RPC на URL из события endpoint.
Аутентификация: заголовок X-API-KEY (см. KYA_MCP_API_KEYS в Settings).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.services.mcp_tool_handlers import (
    get_agent_info_handler,
    register_agent_handler,
    verify_intent_handler,
)


def parse_mcp_api_keys(raw: str) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset()
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return frozenset(p for p in parts if p)


async def _unauthorized(send: Send) -> None:
    body = b'{"detail":"Unauthorized"}'
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class McpApiKeyMiddleware:
    """ASGI: проверка X-API-KEY для всех запросов к смонтированному MCP-приложению."""

    def __init__(self, app: Callable[..., Awaitable[None]], settings_factory: Callable[[], Settings]):
        self.app = app
        self._settings_factory = settings_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = self._settings_factory()
        allowed = parse_mcp_api_keys(settings.kya_mcp_api_keys)
        if not allowed:
            await _unauthorized(send)
            return

        raw_headers = scope.get("headers") or ()
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in raw_headers}
        api_key = headers.get("x-api-key")
        if api_key not in allowed:
            await _unauthorized(send)
            return

        await self.app(scope, receive, send)


def build_kya_http_fastmcp() -> FastMCP:
    """FastMCP с отключённой DNS-rebinding проверкой (защита — API Key + reverse proxy)."""

    mcp = FastMCP(
        "KYA",
        instructions=(
            "KYA (Know Your Agent): verify_intent (Gemini + Solana), register_agent, get_agent_info."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool(
        name="verify_intent",
        description="Анализ интента через Gemini; при record_on_chain и настроенном chain — log_intent на Solana.",
    )
    async def verify_intent(
        intent_text: str,
        context_json: str | None = None,
        record_on_chain: bool = True,
        amount: int = 0,
        destination: str | None = None,
        agent_id: str | None = None,
    ) -> str:
        return await verify_intent_handler(
            get_settings(),
            intent_text,
            context_json,
            record_on_chain,
            amount,
            destination,
            agent_id,
        )

    @mcp.tool(
        name="register_agent",
        description="Регистрация агента on-chain: agent_name, max_amount; logger_authority опционально (base58).",
    )
    async def register_agent(
        agent_name: str,
        max_amount: int,
        logger_authority: str | None = None,
        description: str | None = None,
    ) -> str:
        return await register_agent_handler(
            get_settings(),
            agent_name,
            max_amount,
            logger_authority,
            description,
        )

    @mcp.tool(
        name="get_agent_info",
        description="AgentRecord для кошелька сервера (SOLANA_PRIVATE_KEY / KYA_KEYPAIR_PATH).",
    )
    async def get_agent_info() -> str:
        return await get_agent_info_handler(get_settings())

    return mcp


def create_mcp_starlette_app() -> Starlette:
    """Маршруты `/sse` (GET) и `/messages/` (POST) на базе `SseServerTransport` (как в mcp.server.sse)."""
    fm = build_kya_http_fastmcp()
    mcp_server = fm._mcp_server  # MCPServer из FastMCP; инструменты зарегистрированы на нём
    sse = SseServerTransport(
        "/messages/",
        security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    async def handle_sse(scope: Scope, receive: Receive, send: Send) -> Response:
        async with sse.connect_sse(scope, receive, send) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options(),
            )
        return Response()

    async def sse_endpoint(request: Request) -> Response:
        return await handle_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        )

    return Starlette(
        routes=[
            Route("/sse", endpoint=sse_endpoint, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


def create_mcp_asgi_stack() -> Callable[..., Awaitable[None]]:
    inner = create_mcp_starlette_app()
    return McpApiKeyMiddleware(inner, get_settings)


mcp_asgi_app = create_mcp_asgi_stack()
