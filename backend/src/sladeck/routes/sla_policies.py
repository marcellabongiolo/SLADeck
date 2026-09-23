from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_organization_membership, require_roles
from ..models import Membership, MembershipRole, Request, SLAPolicy
from ..schemas import SLAPolicyCreate, SLAPolicyRead, SLAPolicyUpdate

router = APIRouter(
    prefix="/organizations/{organization_id}/sla-policies",
    tags=["sla-policies"],
)


def get_policy_or_404(
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SLA policy not found",
        )
    return policy


@router.get("", response_model=list[SLAPolicyRead])
def list_policies(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SLAPolicy]:
    statement = (
        select(SLAPolicy)
        .where(SLAPolicy.organization_id == organization_id)
        .order_by(SLAPolicy.name)
    )
    return list(session.scalars(statement))


@router.post("", response_model=SLAPolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(
    organization_id: uuid.UUID,
    payload: SLAPolicyCreate,
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
) -> SLAPolicy:
    policy = SLAPolicy(
        organization_id=organization_id,
        name=payload.name.strip(),
        first_response_minutes=payload.first_response_minutes,
        resolution_minutes=payload.resolution_minutes,
    )
    session.add(policy)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An SLA policy with this name already exists",
        ) from exc
    session.refresh(policy)
    return policy


@router.get("/{policy_id}", response_model=SLAPolicyRead)
def get_policy(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> SLAPolicy:
    return get_policy_or_404(session, organization_id, policy_id)


@router.patch("/{policy_id}", response_model=SLAPolicyRead)
def update_policy(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    payload: SLAPolicyUpdate,
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
) -> SLAPolicy:
    policy = get_policy_or_404(session, organization_id, policy_id)

    new_first = payload.first_response_minutes or policy.first_response_minutes
    new_resolution = payload.resolution_minutes or policy.resolution_minutes
    if new_resolution < new_first:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resolution_minutes must be >= first_response_minutes",
        )

    if payload.name is not None:
        policy.name = payload.name.strip()
    if payload.first_response_minutes is not None:
        policy.first_response_minutes = payload.first_response_minutes
    if payload.resolution_minutes is not None:
        policy.resolution_minutes = payload.resolution_minutes

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An SLA policy with this name already exists",
        ) from exc
    session.refresh(policy)
    return policy


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(
    organization_id: uuid.UUID,
    policy_id: uuid.UUID,
    membership: Annotated[
        Membership,
        Depends(require_roles(MembershipRole.owner, MembershipRole.admin)),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    policy = get_policy_or_404(session, organization_id, policy_id)
    in_use = session.scalar(
        select(Request.id).where(
            Request.organization_id == organization_id,
            Request.sla_policy_id == policy.id,
        )
    )
    if in_use is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SLA policy is in use by one or more requests",
        )

    session.delete(policy)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
