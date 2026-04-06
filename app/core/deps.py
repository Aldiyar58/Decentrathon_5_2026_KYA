from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.gemini import GeminiService
from app.services.solana import SolanaService


def get_gemini_service(settings: Settings = Depends(get_settings)) -> GeminiService:
    return GeminiService(settings)


def get_solana_service(settings: Settings = Depends(get_settings)) -> SolanaService:
    return SolanaService(settings)
