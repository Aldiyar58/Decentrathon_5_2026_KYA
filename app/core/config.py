from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    solana_rpc_url: str = "https://api.devnet.solana.com"
    solana_private_key: str = ""
    kya_keypair_path: str | None = None
    kya_program_id: str = ""
    kya_idl_path: str = Field(
        default_factory=lambda: str(_BACKEND_ROOT / "idl" / "kya_program.json"),
    )
    # Logger authority: если не задан отдельный ключ — используется owner (SOLANA_PRIVATE_KEY / KYA_KEYPAIR_PATH).
    kya_logger_authority: str = ""
    kya_logger_private_key: str = ""
    kya_logger_keypair_path: str | None = None

    # HTTP MCP (SSE): список ключей через запятую или `;`. Пусто — все запросы к /mcp/* отклоняются (401).
    kya_mcp_api_keys: str = ""

    # Eliza: базовый URL REST (например http://localhost:3000). Пусто — spawn пропускается с ошибкой в ответе.
    eliza_api_url: str = ""
    eliza_api_key: str = ""
    # URL SSE MCP для встраивания в character Eliza; ключ, который Eliza передаёт в заголовке X-API-KEY к KYA MCP.
    kya_mcp_sse_url: str = ""
    kya_mcp_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
