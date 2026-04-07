import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router
from app.api.mcp import mcp_asgi_app

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="KYA API", version="0.0.1")

    origins = [
        "http://localhost:5173",  # Стандартный порт Vite (локально)
        "https://nis-edu-scope-front.vercel.app/",  # Твой будущий адрес на Vercel
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],  # Разрешаем все методы (GET, POST и т.д.)
        allow_headers=["*"],  # Разрешаем все заголовки
    )
    app.include_router(router)
    app.mount("/mcp", mcp_asgi_app)
    return app


app = create_app()
