from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import record_audit_event
from .models import Request, RequestStatus, SLANotification
from .sla import calculate_sla_state


def _notification_payload(request: Request, stage: str, kind: str, due_at: datetime) -> dict[str, Any]:
    return {
        "request_title": request.title,
        "stage": stage,
        "kind": kind,
        "due_at": due_at.isoformat(),
        "worker": "celery",
    }


def _create_notification(
    session: Session,
    *,
    request: Request,
    stage: str,
    kind: str,
    due_at: datetime,
) -> SLANotification | None:
    existing = session.scalar(
        select(SLANotification.id).where(
            SLANotification.request_id == request.id,
            SLANotification.stage == stage,
            SLANotification.kind == kind,
        )
    )
    if existing is not None:
        return None

    notification = SLANotification(
        organization_id=request.organization_id,
        request_id=request.id,
        stage=stage,
        kind=kind,
        due_at=due_at,
        data=_notification_payload(request, stage, kind, due_at),
    )

    try:
        with session.begin_nested():
            session.add(notification)
            session.flush()
            record_audit_event(
                session,
                organization_id=request.organization_id,
                request_id=request.id,
                actor_user_id=None,
                event_type=f"sla_{kind}_created",
                data={
                    "notification_id": notification.id,
                    "stage": stage,
                    "due_at": due_at,
                },
            )
    except IntegrityError:
        # Another worker may have created the same escalation concurrently.
        return None

    return notification


def run_sla_check(
    session: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    requests = list(
        session.scalars(
            select(Request).where(
                Request.status.notin_(
                    [RequestStatus.resolved, RequestStatus.closed]
                )
            )
        )
    )

    created = 0
    for request in requests:
        if request.first_responded_at is None and request.first_response_due_at is not None:
            state = calculate_sla_state(
                status=request.status,
                created_at=request.created_at,
                first_response_due_at=request.first_response_due_at,
                first_responded_at=request.first_responded_at,
                resolution_due_at=request.resolution_due_at,
                resolved_at=request.resolved_at,
                now=current,
            )
            due_at = request.first_response_due_at
            stage = "first_response"
        elif request.resolution_due_at is not None:
            state = calculate_sla_state(
                status=request.status,
                created_at=request.created_at,
                first_response_due_at=request.first_response_due_at,
                first_responded_at=request.first_responded_at,
                resolution_due_at=request.resolution_due_at,
                resolved_at=request.resolved_at,
                now=current,
            )
            due_at = request.resolution_due_at
            stage = "resolution"
        else:
            continue

        if state not in {"warning", "breached"}:
            continue

        notification = _create_notification(
            session,
            request=request,
            stage=stage,
            kind=state,
            due_at=due_at,
        )
        if notification is not None:
            created += 1

    session.commit()
    return {"checked": len(requests), "created": created}
