"""
MCP-сервер KYA (stdio). Инструменты: verify_intent, get_credential, register_agent, get_agent_info.

Запуск из корня репозитория (где лежит `app/` и `requirements.txt`):
    python -m app.mcp.server

HTTP/SSE: см. `app.api.mcp`, mount `/mcp` в FastAPI.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from app.core.config import get_settings
from app.services.mcp_tool_handlers import (
    get_agent_info_handler,
    get_credential_handler,
    register_agent_handler,
    verify_intent_handler,
)

logging.basicConfig(level=logging.INFO)

mcp = FastMCP(
    "KYA",
    instructions="KYA (Know Your Agent): проверка интентов через Gemini и учёт на Solana.",
)


@mcp.tool(
    name="verify_intent",
    description="Анализ интента через Gemini; при настроенном chain — log_intent на Solana (u8 decision + reasoning + amount + destination).",
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
    name="get_credential",
    description="Данные AgentRecord по owner pubkey (base58).",
)
async def get_credential(owner_pubkey: str) -> str:
    return await get_credential_handler(get_settings(), owner_pubkey)


@mcp.tool(
    name="register_agent",
    description="Регистрация агента: agent_name, max_amount; logger_authority и description опционально.",
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
    description="AgentRecord для кошелька процесса (SOLANA_PRIVATE_KEY / KYA_KEYPAIR_PATH).",
)
async def get_agent_info() -> str:
    return await get_agent_info_handler(get_settings())


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
