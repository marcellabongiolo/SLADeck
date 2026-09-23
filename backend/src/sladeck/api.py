from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes.auth import router as auth_router
from .routes.organizations import router as organizations_router
from .routes.request_activity import router as request_activity_router
from .routes.requests import router as requests_router
from .routes.sla_notifications import router as sla_notifications_router
from .routes.sla_policies import router as sla_policies_router
from .routes.analytics import router as analytics_router


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
    app.include_router(auth_router)
    app.include_router(organizations_router)
    app.include_router(sla_policies_router)
    app.include_router(requests_router)
    app.include_router(request_activity_router)
    app.include_router(sla_notifications_router)
    app.include_router(analytics_router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "sladeck-api",
            "environment": settings.environment,
        }

    return app


app = create_app()
