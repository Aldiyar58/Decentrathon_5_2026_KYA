import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="KYA API", version="0.0.1")

    origins = [
        "http://localhost:5173",  # Стандартный порт Vite (локально)
        "https://nis-edu-scope-front.vercel.app/",  # Твой будущий адрес на Vercel
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],  # Разрешаем все методы (GET, POST и т.д.)
        allow_headers=["*"],  # Разрешаем все заголовки
    )
    app.include_router(router)
    return app


app = create_app()
