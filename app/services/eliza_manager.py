"""Eliza REST: генерация character.json и POST активации инстанса."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ElizaSpawnResult:
    ok: bool
    eliza_agent_id: str | None = None
    error: str | None = None
    http_status: int | None = None


class ElizaManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_character_json(self, name: str, description: str, agent_id: str) -> dict[str, Any]:
        desc = description.strip()
        bio = [desc] if desc else [f"KYA-registered agent: {name}"]
        lore = [desc] if desc else []

        secrets: dict[str, str] = {}
        sse = self._settings.kya_mcp_sse_url.strip()
        mcp_key = self._settings.kya_mcp_api_key.strip()
        if sse:
            secrets["KYA_MCP_SSE_URL"] = sse
        if mcp_key:
            secrets["KYA_MCP_API_KEY"] = mcp_key

        character: dict[str, Any] = {
            "name": name.strip() or "KYA Agent",
            "bio": bio,
            "lore": lore,
            "settings": {
                "secrets": secrets,
            },
        }
        # Стабильный id для Eliza (KYA owner pubkey)
        character["id"] = agent_id.strip()
        return character

    async def spawn_agent_request(
        self,
        name: str,
        description: str,
        agent_id: str,
    ) -> ElizaSpawnResult:
        base = self._settings.eliza_api_url.strip().rstrip("/")
        if not base:
            return ElizaSpawnResult(
                ok=False,
                error="ELIZA_API_URL is not configured",
                http_status=None,
            )

        character = self.build_character_json(name, description, agent_id)
        url = f"{base}/agents/{agent_id}/set"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._settings.eliza_api_key.strip():
            headers["Authorization"] = f"Bearer {self._settings.eliza_api_key.strip()}"

        payload: dict[str, Any] = {"character": character}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as e:
            logger.warning("Eliza spawn request failed: %s", e)
            return ElizaSpawnResult(ok=False, error=str(e), http_status=None)

        status = response.status_code
        body: Any = None
        try:
            body = response.json()
        except Exception:
            body = None

        if status >= 400:
            err = (
                body.get("error", body.get("message", response.text[:500]))
                if isinstance(body, dict)
                else response.text[:500]
            )
            return ElizaSpawnResult(ok=False, error=str(err), http_status=status)

        eliza_id = None
        if isinstance(body, dict):
            eliza_id = body.get("id") or body.get("agentId") or body.get("agent_id")
            nested = body.get("data")
            if eliza_id is None and isinstance(nested, dict):
                eliza_id = nested.get("id") or nested.get("agentId")
        if eliza_id is None:
            eliza_id = agent_id

        return ElizaSpawnResult(ok=True, eliza_agent_id=str(eliza_id), http_status=status)
