from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="API for the SLADeck multi-tenant request and SLA management SaaS.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "sladeck-api",
            "environment": settings.environment,
        }

    return app


app = create_app()
