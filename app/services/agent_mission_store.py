"""In-memory agent_id (owner pubkey base58) → registration mission (description).

v1: процесс один; для нескольких воркеров заменить на Redis/БД.
"""

from __future__ import annotations

_missions: dict[str, str] = {}


def set_mission(agent_id: str, description: str) -> None:
    _missions[agent_id.strip()] = description.strip()


def get_mission(agent_id: str) -> str | None:
    return _missions.get(agent_id.strip())


def delete_mission(agent_id: str) -> None:
    _missions.pop(agent_id.strip(), None)


def clear_all_missions() -> None:
    """Только для тестов."""
    _missions.clear()
