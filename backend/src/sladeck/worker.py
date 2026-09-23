from __future__ import annotations

from datetime import datetime
from uuid import UUID

from celery import Celery

from .config import get_settings
from .db import Base  # noqa: F401
from .escalations import run_sla_check
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

settings = get_settings()

celery_app = Celery(
    "sladeck",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    beat_schedule={
        "check-sla-deadlines-every-minute": {
            "task": "sladeck.check_sla_deadlines",
            "schedule": 60.0,
        }
    },
)


@celery_app.task(
    bind=True,
    name="sladeck.check_sla_deadlines",
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def check_sla_deadlines(self, now_iso: str | None = None) -> dict[str, int]:
    current = datetime.fromisoformat(now_iso) if now_iso else None
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            return run_sla_check(session, now=current)
    finally:
        engine.dispose()
