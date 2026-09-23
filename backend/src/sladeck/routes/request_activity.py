from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit_event
from ..db import get_db
from ..dependencies import get_organization_membership
from ..models import AuditEvent, Comment, Membership, Request
from ..schemas import ActivityItem, CommentCreate, CommentRead

router = APIRouter(
    prefix="/organizations/{organization_id}/requests/{request_id}",
    tags=["request-activity"],
)


def get_request_or_404(
    session: Session,
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
) -> Request:
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
    return request


@router.get("/comments", response_model=list[CommentRead])
def list_comments(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> list[Comment]:
    get_request_or_404(session, organization_id, request_id)
    statement = (
        select(Comment)
        .where(
            Comment.organization_id == organization_id,
            Comment.request_id == request_id,
        )
        .order_by(Comment.created_at, Comment.id)
    )
    return list(session.scalars(statement))


@router.post("/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: CommentCreate,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> Comment:
    get_request_or_404(session, organization_id, request_id)

    comment = Comment(
        organization_id=organization_id,
        request_id=request_id,
        author_id=membership.user_id,
        body=payload.body.strip(),
    )
    session.add(comment)
    session.flush()

    record_audit_event(
        session,
        organization_id=organization_id,
        request_id=request_id,
        actor_user_id=membership.user_id,
        event_type="comment_added",
        data={"comment_id": comment.id},
    )

    session.commit()
    session.refresh(comment)
    return comment


@router.get("/activity", response_model=list[ActivityItem])
def activity_timeline(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> list[ActivityItem]:
    get_request_or_404(session, organization_id, request_id)

    comments = list(
        session.scalars(
            select(Comment).where(
                Comment.organization_id == organization_id,
                Comment.request_id == request_id,
            )
        )
    )
    events = list(
        session.scalars(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.request_id == request_id,
                AuditEvent.event_type != "comment_added",
            )
        )
    )

    items: list[ActivityItem] = [
        ActivityItem(
            kind="comment",
            id=comment.id,
            actor_user_id=comment.author_id,
            body=comment.body,
            created_at=comment.created_at,
        )
        for comment in comments
    ]
    items.extend(
        ActivityItem(
            kind="audit_event",
            id=event.id,
            actor_user_id=event.actor_user_id,
            event_type=event.event_type,
            data=event.data,
            created_at=event.created_at,
        )
        for event in events
    )
    return sorted(items, key=lambda item: (item.created_at, str(item.id)))
