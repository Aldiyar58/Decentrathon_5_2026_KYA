import logging

from fastapi import FastAPI

from app.api.endpoints import router

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(title="KYA API", version="0.0.1")
    app.include_router(router)
    return app


app = create_app()
