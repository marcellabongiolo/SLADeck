from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .models import AuthSession, User
from .schemas import TokenPair
from .security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password_or_dummy,
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    normalized = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized))
    valid = verify_password_or_dummy(password, user.password_hash if user else None)
    if user is None or not valid:
        return None
    return user


def issue_token_pair(session: Session, user: User, settings: Settings) -> TokenPair:
    refresh_token = new_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)

    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
    )
    session.add(auth_session)
    session.flush()

    return TokenPair(
        access_token=create_access_token(user.id, settings),
        refresh_token=refresh_token,
        expires_in=settings.access_token_minutes * 60,
    )


def rotate_refresh_token(
    session: Session,
    refresh_token: str,
    settings: Settings,
) -> TokenPair | None:
    token_hash = hash_refresh_token(refresh_token)
    auth_session = session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash)
        .with_for_update()
    )

    now = datetime.now(timezone.utc)
    if auth_session is None:
        return None
    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        return None

    auth_session.revoked_at = now
    user = session.get(User, auth_session.user_id)
    if user is None:
        return None
    return issue_token_pair(session, user, settings)


def revoke_refresh_token(session: Session, refresh_token: str) -> bool:
    token_hash = hash_refresh_token(refresh_token)
    auth_session = session.scalar(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == token_hash)
        .with_for_update()
    )
    if auth_session is None:
        return False

    if auth_session.revoked_at is None:
        auth_session.revoked_at = datetime.now(timezone.utc)
    return True
