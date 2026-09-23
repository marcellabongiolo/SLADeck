from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import MembershipRole


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
