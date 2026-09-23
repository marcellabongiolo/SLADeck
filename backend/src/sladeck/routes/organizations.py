from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user, get_organization_membership, require_roles
from ..models import Membership, MembershipRole, Organization, User
from ..schemas import (
    MembershipAdd,
    MembershipRead,
    MembershipRoleUpdate,
    OrganizationCreate,
    OrganizationRead,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def membership_to_read(membership: Membership) -> MembershipRead:
    return MembershipRead(
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[Organization]:
    statement = (
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == current_user.id)
        .order_by(Organization.name)
    )
    return list(session.scalars(statement))


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Organization:
    organization = Organization(name=payload.name.strip(), slug=payload.slug)
    session.add(organization)
    session.flush()
    session.add(
        Membership(
            user_id=current_user.id,
            organization_id=organization.id,
            role=MembershipRole.owner,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        ) from exc
    session.refresh(organization)
    return organization


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: uuid.UUID,
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.get("/{organization_id}/members", response_model=list[MembershipRead])
def list_members(
    membership: Annotated[Membership, Depends(get_organization_membership)],
    session: Annotated[Session, Depends(get_db)],
) -> list[MembershipRead]:
    members = list(
        session.scalars(
            select(Membership)
            .where(Membership.organization_id == membership.organization_id)
            .order_by(Membership.created_at)
        )
    )
    return [membership_to_read(item) for item in members]


@router.post(
    "/{organization_id}/members",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    payload: MembershipAdd,
    actor: Annotated[
        Membership,
        Depends(require_roles(MembershipRole.owner, MembershipRole.admin)),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> MembershipRead:
    if actor.role == MembershipRole.admin and payload.role == MembershipRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot create other admins",
        )

    user = session.scalar(
        select(User).where(User.email == str(payload.email).strip().lower())
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = session.scalar(
        select(Membership).where(
            Membership.organization_id == actor.organization_id,
            Membership.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member",
        )

    membership = Membership(
        user_id=user.id,
        organization_id=actor.organization_id,
        role=payload.role,
    )
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return membership_to_read(membership)


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=MembershipRead,
)
def update_member_role(
    user_id: uuid.UUID,
    payload: MembershipRoleUpdate,
    actor: Annotated[
        Membership,
        Depends(require_roles(MembershipRole.owner, MembershipRole.admin)),
    ],
    session: Annotated[Session, Depends(get_db)],
) -> MembershipRead:
    target = session.scalar(
        select(Membership).where(
            Membership.organization_id == actor.organization_id,
            Membership.user_id == user_id,
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.user_id == actor.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )
    if target.role == MembershipRole.owner or payload.role == MembershipRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role changes require a dedicated ownership-transfer flow",
        )
    if actor.role == MembershipRole.admin and (
        target.role == MembershipRole.admin or payload.role == MembershipRole.admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot manage admin roles",
        )

    target.role = payload.role
    session.commit()
    session.refresh(target)
    return membership_to_read(target)
