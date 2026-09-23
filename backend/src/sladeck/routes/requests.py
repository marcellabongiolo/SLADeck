from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit_event
from ..db import get_db
from ..dependencies import get_organization_membership, require_roles
from ..models import (
    Membership,
    MembershipRole,
    Request,
    RequestPriority,
    RequestStatus,
    SLAPolicy,
)
from ..schemas import RequestCreate, RequestRead, RequestUpdate
from ..sla import calculate_deadlines, calculate_sla_state, validate_status_transition

router = APIRouter(
    prefix="/organizations/{organization_id}/requests",
    tags=["requests"],
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


def get_policy_or_400(
    session: Session,
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
) -> SLAPolicy:
    policy = session.scalar(
        select(SLAPolicy).where(
            SLAPolicy.id == policy_id,
            SLAPolicy.organization_id == organization_id,
        )
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SLA policy does not belong to this organization",
        )
    return policy


def ensure_assignee_membership(
    session: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    if user_id is None:
        return

    membership = session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee does not belong to this organization",
        )


def request_to_read(request: Request, now: datetime | None = None) -> RequestRead:
    return RequestRead(
        id=request.id,
        organization_id=request.organization_id,
        title=request.title,
        description=request.description,
        status=request.status,
        priority=request.priority,
        requester_id=request.requester_id,
        assignee_id=request.assignee_id,
        sla_policy_id=request.sla_policy_id,
        first_response_due_at=request.first_response_due_at,
        first_responded_at=request.first_responded_at,
        resolution_due_at=request.resolution_due_at,
        resolved_at=request.resolved_at,
        created_at=request.created_at,
        updated_at=request.updated_at,
        sla_state=calculate_sla_state(
            status=request.status,
            created_at=request.created_at,
            first_response_due_at=request.first_response_due_at,
            first_responded_at=request.first_responded_at,
            resolution_due_at=request.resolution_due_at,
            resolved_at=request.resolved_at,
            now=now,
        ),
    )


def recalculate_deadlines(request: Request, policy: SLAPolicy) -> None:
    deadlines = calculate_deadlines(
        request.created_at,
        request.priority,
        policy.first_response_minutes,
        policy.resolution_minutes,
    )
    request.first_response_due_at = deadlines.first_response_due_at
    request.resolution_due_at = deadlines.resolution_due_at


@router.get("", response_model=list[RequestRead])
def list_requests(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
    request_status: Annotated[RequestStatus | None, Query(alias="status")] = None,
    priority: RequestPriority | None = None,
    assignee_id: uuid.UUID | None = None,
) -> list[RequestRead]:
    statement = select(Request).where(Request.organization_id == organization_id)
    if request_status is not None:
        statement = statement.where(Request.status == request_status)
    if priority is not None:
        statement = statement.where(Request.priority == priority)
    if assignee_id is not None:
        statement = statement.where(Request.assignee_id == assignee_id)

    statement = statement.order_by(Request.created_at.desc())
    return [request_to_read(item) for item in session.scalars(statement)]


@router.post("", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    organization_id: uuid.UUID,
    payload: RequestCreate,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> RequestRead:
    policy = get_policy_or_400(session, organization_id, payload.sla_policy_id)
    ensure_assignee_membership(session, organization_id, payload.assignee_id)

    request = Request(
        organization_id=organization_id,
        title=payload.title.strip(),
        description=payload.description,
        priority=payload.priority,
        requester_id=membership.user_id,
        assignee_id=payload.assignee_id,
        sla_policy_id=policy.id,
    )
    session.add(request)
    session.flush()
    recalculate_deadlines(request, policy)
    record_audit_event(
        session,
        organization_id=organization_id,
        request_id=request.id,
        actor_user_id=membership.user_id,
        event_type="request_created",
        data={
            "title": request.title,
            "priority": request.priority,
            "assignee_id": request.assignee_id,
            "sla_policy_id": request.sla_policy_id,
        },
    )
    session.commit()
    session.refresh(request)
    return request_to_read(request)


@router.get("/{request_id}", response_model=RequestRead)
def get_request(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> RequestRead:
    return request_to_read(get_request_or_404(session, organization_id, request_id))


@router.patch("/{request_id}", response_model=RequestRead)
def update_request(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: RequestUpdate,
    membership: Annotated[
        Membership,
        Depends(
            require_roles(
                MembershipRole.owner,
                MembershipRole.admin,
                MembershipRole.manager,
            )
        ),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> RequestRead:
    request = get_request_or_404(session, organization_id, request_id)
    previous_status = request.status
    previous_priority = request.priority
    previous_assignee_id = request.assignee_id
    previous_sla_policy_id = request.sla_policy_id

    if payload.status is not None:
        try:
            validate_status_transition(request.status, payload.status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    if "assignee_id" in payload.model_fields_set:
        ensure_assignee_membership(session, organization_id, payload.assignee_id)

    policy = request.sla_policy
    if "sla_policy_id" in payload.model_fields_set:
        if payload.sla_policy_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A request must have an SLA policy",
            )
        policy = get_policy_or_400(session, organization_id, payload.sla_policy_id)

    if payload.title is not None:
        request.title = payload.title.strip()
    if payload.description is not None:
        request.description = payload.description
    if payload.priority is not None:
        request.priority = payload.priority
    if "assignee_id" in payload.model_fields_set:
        request.assignee_id = payload.assignee_id
    if "sla_policy_id" in payload.model_fields_set and policy is not None:
        request.sla_policy_id = policy.id

    if payload.status is not None and payload.status != request.status:
        previous = request.status
        request.status = payload.status
        if payload.status == RequestStatus.resolved:
            request.resolved_at = datetime.now(timezone.utc)
        elif previous == RequestStatus.resolved and payload.status == RequestStatus.in_progress:
            request.resolved_at = None

    if (
        payload.priority is not None
        or "sla_policy_id" in payload.model_fields_set
    ) and policy is not None:
        recalculate_deadlines(request, policy)

    if request.status != previous_status:
        record_audit_event(
            session,
            organization_id=organization_id,
            request_id=request.id,
            actor_user_id=membership.user_id,
            event_type="status_changed",
            data={"from": previous_status, "to": request.status},
        )
    if request.priority != previous_priority:
        record_audit_event(
            session,
            organization_id=organization_id,
            request_id=request.id,
            actor_user_id=membership.user_id,
            event_type="priority_changed",
            data={"from": previous_priority, "to": request.priority},
        )
    if request.assignee_id != previous_assignee_id:
        record_audit_event(
            session,
            organization_id=organization_id,
            request_id=request.id,
            actor_user_id=membership.user_id,
            event_type="assignee_changed",
            data={"from": previous_assignee_id, "to": request.assignee_id},
        )
    if request.sla_policy_id != previous_sla_policy_id:
        record_audit_event(
            session,
            organization_id=organization_id,
            request_id=request.id,
            actor_user_id=membership.user_id,
            event_type="sla_policy_changed",
            data={"from": previous_sla_policy_id, "to": request.sla_policy_id},
        )

    session.commit()
    session.refresh(request)
    return request_to_read(request)


@router.post("/{request_id}/first-response", response_model=RequestRead)
def mark_first_response(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> RequestRead:
    request = get_request_or_404(session, organization_id, request_id)

    if (
        membership.role == MembershipRole.member
        and request.assignee_id != membership.user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assignee or an elevated role can mark first response",
        )

    if request.first_responded_at is None:
        request.first_responded_at = datetime.now(timezone.utc)
        record_audit_event(
            session,
            organization_id=organization_id,
            request_id=request.id,
            actor_user_id=membership.user_id,
            event_type="first_response_recorded",
            data={"first_responded_at": request.first_responded_at},
        )
        session.commit()
        session.refresh(request)

    return request_to_read(request)


@router.delete("/{request_id}", status_code=status.HTTP_409_CONFLICT)
def delete_request(
    organization_id: uuid.UUID,
    request_id: uuid.UUID,
    membership: Annotated[
        Membership,
        Depends(require_roles(MembershipRole.owner, MembershipRole.admin)),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> None:
    get_request_or_404(session, organization_id, request_id)
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Requests are retained for audit history; close the request instead",
    )
