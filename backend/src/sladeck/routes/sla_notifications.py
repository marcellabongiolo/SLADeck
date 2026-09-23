from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_organization_membership
from ..models import Membership, Request, SLANotification
from ..schemas import SLANotificationRead

router = APIRouter(
    prefix="/organizations/{organization_id}/requests/{request_id}",
    tags=["sla-notifications"],
)


@router.get("/sla-notifications", response_model=list[SLANotificationRead])
def list_sla_notifications(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SLANotification]:
    request = session.scalar(
        select(Request).where(
            Request.id == request_id,
            Request.organization_id == organization_id,
        )
    )
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    statement = (
        select(SLANotification)
        .where(
            SLANotification.organization_id == organization_id,
            SLANotification.request_id == request_id,
        )
        .order_by(SLANotification.created_at, SLANotification.id)
    )
    return list(session.scalars(statement))
