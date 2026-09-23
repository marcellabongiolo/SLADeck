from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class MembershipRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    manager = "manager"
    member = "member"


class RequestStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    waiting = "waiting"
    resolved = "resolved"
    closed = "closed"


class RequestPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    sla_policies: Mapped[list["SLAPolicy"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    requests: Mapped[list["Request"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        Index("ix_memberships_organization_role", "organization_id", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role"),
        nullable=False,
        default=MembershipRole.member,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")


class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_sla_policy_org_name"),
        Index("ix_sla_policies_organization_id", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="sla_policies")
    requests: Mapped[list["Request"]] = relationship(back_populates="sla_policy")


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["requester_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_requests_requester_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignee_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_requests_assignee_membership",
            ondelete="RESTRICT",
        ),
        Index("ix_requests_org_status", "organization_id", "status"),
        Index("ix_requests_org_priority", "organization_id", "priority"),
        Index("ix_requests_org_assignee", "organization_id", "assignee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        nullable=False,
        default=RequestStatus.open,
    )
    priority: Mapped[RequestPriority] = mapped_column(
        Enum(RequestPriority, name="request_priority"),
        nullable=False,
        default=RequestPriority.normal,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("sla_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    first_response_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped[Organization] = relationship(back_populates="requests")
    sla_policy: Mapped[SLAPolicy | None] = relationship(back_populates="requests")
