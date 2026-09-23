from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_organization_membership
from ..models import Membership, Request, RequestPriority, RequestStatus, SLANotification
from ..schemas import SLAAnalyticsRead, NotificationRead
from ..sla import calculate_sla_state

router = APIRouter(prefix="/organizations/{organization_id}", tags=["analytics"])


def _range(
    start: datetime | None,
    end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if start is None and end is None:
        return None, None
    now = datetime.now(timezone.utc)
    return start or now - timedelta(days=30), end or now


@router.get("/analytics", response_model=SLAAnalyticsRead)
def analytics(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
    start: datetime | None = None,
    end: datetime | None = None,
):
    start, end = _range(start, end)
    filters = [Request.organization_id == organization_id]
    if start:
        filters.append(Request.created_at >= start)
    if end:
        filters.append(Request.created_at <= end)

    requests = list(session.scalars(select(Request).where(*filters)))
    counts = {status.value: 0 for status in RequestStatus}
    priorities = {priority.value: 0 for priority in RequestPriority}
    workload: dict[str, int] = {}
    healthy = warning = breached = 0

    for request in requests:
        counts[request.status.value] += 1
        priorities[request.priority.value] += 1
        assignee = str(request.assignee_id) if request.assignee_id else "unassigned"
        workload[assignee] = workload.get(assignee, 0) + 1

        state = calculate_sla_state(
            status=request.status,
            created_at=request.created_at,
            first_response_due_at=request.first_response_due_at,
            first_responded_at=request.first_responded_at,
            resolution_due_at=request.resolution_due_at,
            resolved_at=request.resolved_at,
        )
        if state == "warning":
            warning += 1
        elif state == "breached":
            breached += 1
        else:
            healthy += 1

    total = healthy + warning + breached
    memberships = session.scalars(
        select(Membership).where(Membership.organization_id == organization_id)
    )
    names = {member.user_id: member.user.full_name for member in memberships}
    assignees = [
        {
            "assignee_id": assignee_id,
            "name": (
                names.get(uuid.UUID(assignee_id), "Unassigned")
                if assignee_id != "unassigned"
                else "Unassigned"
            ),
            "count": count,
        }
        for assignee_id, count in workload.items()
    ]

    return SLAAnalyticsRead(
        open_requests=sum(counts[status] for status in ("open", "in_progress", "waiting")),
        healthy_requests=healthy,
        warning_requests=warning,
        breached_requests=breached,
        breach_rate_pct=round(breached / total * 100, 2) if total else 0.0,
        by_status=counts,
        by_priority=priorities,
        by_assignee=assignees,
        period_start=start,
        period_end=end,
    )


@router.get("/notifications", response_model=list[NotificationRead])
def notifications(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
):
    rows = session.execute(
        select(SLANotification, Request.title)
        .join(Request, Request.id == SLANotification.request_id)
        .where(SLANotification.organization_id == organization_id)
        .order_by(SLANotification.created_at.desc())
        .limit(50)
    )
    return [
        NotificationRead.model_validate(notification, from_attributes=True).model_copy(
            update={
                "title": title,
                "message": (
                    f"{notification.stage.replace('_', ' ').title()} "
                    f"SLA {notification.kind}"
                ),
            }
        )
        for notification, title in rows
    ]
