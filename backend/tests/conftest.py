from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from sladeck.api import create_app
from sladeck.db import Base


@pytest.fixture
def postgres_url() -> str:
    url = os.getenv("SLADECK_DATABASE_URL")
    if not url:
        pytest.skip("SLADECK_DATABASE_URL is required for PostgreSQL integration tests")
    return url


@pytest.fixture
def db_engine(postgres_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(postgres_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    with Session(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    with TestClient(create_app()) as test_client:
        yield test_client
