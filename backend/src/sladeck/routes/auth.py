from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    authenticate_user,
    issue_token_pair,
    normalize_email,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..config import Settings, get_settings
from ..db import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserRead,
)
from ..security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    email = normalize_email(str(payload.email))
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPair:
    user = authenticate_user(session, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    tokens = issue_token_pair(session, user, settings)
    session.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(
    payload: RefreshRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPair:
    tokens = rotate_refresh_token(session, payload.refresh_token, settings)
    if tokens is None:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    session.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    revoke_refresh_token(session, payload.refresh_token)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
