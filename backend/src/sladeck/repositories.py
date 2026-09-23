from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Request


def list_requests_for_organization(
    session: Session,
    organization_id: uuid.UUID,
) -> list[Request]:
    """Return requests for exactly one tenant.

    Keeping organization_id explicit in repository queries prevents accidental
    unscoped reads as the API grows.
    """
    statement = (
        select(Request)
        .where(Request.organization_id == organization_id)
        .order_by(Request.created_at.desc())
    )
    return list(session.scalars(statement))
