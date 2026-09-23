from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .models import MembershipRole, RequestPriority, RequestStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime


class MembershipAdd(BaseModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.member

    @field_validator("role")
    @classmethod
    def owner_cannot_be_invited_directly(cls, value: MembershipRole) -> MembershipRole:
        if value == MembershipRole.owner:
            raise ValueError("Owner role cannot be assigned through member creation")
        return value


class MembershipRoleUpdate(BaseModel):
    role: MembershipRole


class MembershipRead(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: MembershipRole
    created_at: datetime



class SLAPolicyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    first_response_minutes: int = Field(gt=0, le=43200)
    resolution_minutes: int = Field(gt=0, le=525600)

    @model_validator(mode="after")
    def validate_durations(self) -> "SLAPolicyCreate":
        if self.resolution_minutes < self.first_response_minutes:
            raise ValueError("resolution_minutes must be >= first_response_minutes")
        return self


class SLAPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    first_response_minutes: int | None = Field(default=None, gt=0, le=43200)
    resolution_minutes: int | None = Field(default=None, gt=0, le=525600)


class SLAPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    first_response_minutes: int
    resolution_minutes: int
    created_at: datetime
    updated_at: datetime


class RequestCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(default="", max_length=20000)
    priority: RequestPriority = RequestPriority.normal
    assignee_id: uuid.UUID | None = None
    sla_policy_id: uuid.UUID


class RequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    assignee_id: uuid.UUID | None = None
    sla_policy_id: uuid.UUID | None = None


class RequestRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: str
    status: RequestStatus
    priority: RequestPriority
    requester_id: uuid.UUID
    assignee_id: uuid.UUID | None
    sla_policy_id: uuid.UUID | None
    first_response_due_at: datetime | None
    first_responded_at: datetime | None
    resolution_due_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    sla_state: str



class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body")
    @classmethod
    def body_must_contain_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Comment body cannot be blank")
        return stripped


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    request_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    request_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    event_type: str
    data: dict
    created_at: datetime


class ActivityItem(BaseModel):
    kind: str
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    event_type: str | None = None
    body: str | None = None
    data: dict = Field(default_factory=dict)
    created_at: datetime
