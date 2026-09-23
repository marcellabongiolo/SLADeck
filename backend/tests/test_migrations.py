from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError


def test_alembic_builds_core_schema_from_empty_database(postgres_url: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[1] / "alembic"),
    )
    config.set_main_option("sqlalchemy.url", postgres_url)

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(postgres_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "alembic_version",
            "users",
            "organizations",
            "memberships",
            "sla_policies",
            "requests",
            "auth_sessions",
            "comments",
            "audit_events",
        }.issubset(tables)

        request_columns = {column["name"] for column in inspect(engine).get_columns("requests")}
        assert "first_responded_at" in request_columns
    finally:
        engine.dispose()
        command.downgrade(config, "base")



def test_audit_events_are_database_append_only(postgres_url: str) -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option(
        "script_location",
        str(Path(__file__).parents[1] / "alembic"),
    )
    config.set_main_option("sqlalchemy.url", postgres_url)

    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(postgres_url)
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    request_id = uuid.uuid4()
    event_id = uuid.uuid4()

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, full_name, password_hash)
                    VALUES (:id, :email, :name, :password_hash)
                    """
                ),
                {
                    "id": user_id,
                    "email": "audit-db@example.com",
                    "name": "Audit User",
                    "password_hash": "not-a-real-hash",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO organizations (id, name, slug)
                    VALUES (:id, :name, :slug)
                    """
                ),
                {
                    "id": organization_id,
                    "name": "Audit Org",
                    "slug": "audit-org",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO memberships (id, user_id, organization_id, role)
                    VALUES (:id, :user_id, :organization_id, 'owner')
                    """
                ),
                {
                    "id": membership_id,
                    "user_id": user_id,
                    "organization_id": organization_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO requests (
                        id,
                        organization_id,
                        title,
                        description,
                        status,
                        priority,
                        requester_id
                    )
                    VALUES (
                        :id,
                        :organization_id,
                        :title,
                        '',
                        'open',
                        'normal',
                        :requester_id
                    )
                    """
                ),
                {
                    "id": request_id,
                    "organization_id": organization_id,
                    "title": "Audit retention request",
                    "requester_id": user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO audit_events (
                        id,
                        organization_id,
                        request_id,
                        actor_user_id,
                        event_type,
                        data
                    )
                    VALUES (
                        :id,
                        :organization_id,
                        :request_id,
                        :actor_user_id,
                        'request_created',
                        CAST(:data AS json)
                    )
                    """
                ),
                {
                    "id": event_id,
                    "organization_id": organization_id,
                    "request_id": request_id,
                    "actor_user_id": user_id,
                    "data": "{}",
                },
            )

        with engine.connect() as connection:
            with pytest.raises(DBAPIError, match="append-only"):
                connection.execute(
                    text("UPDATE audit_events SET event_type = 'tampered' WHERE id = :id"),
                    {"id": event_id},
                )
                connection.commit()
            connection.rollback()

            with pytest.raises(DBAPIError, match="append-only"):
                connection.execute(
                    text("DELETE FROM audit_events WHERE id = :id"),
                    {"id": event_id},
                )
                connection.commit()
            connection.rollback()
    finally:
        engine.dispose()
        command.downgrade(config, "base")
