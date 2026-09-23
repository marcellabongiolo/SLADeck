from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditEvent


def _serialize(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def record_audit_event(
    session: Session,
    *,
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        request_id=request_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        data={key: _serialize(value) for key, value in (data or {}).items()},
    )
    session.add(event)
    return event
