from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
        }.issubset(tables)

        request_columns = {column["name"] for column in inspect(engine).get_columns("requests")}
        assert "first_responded_at" in request_columns
    finally:
        engine.dispose()
        command.downgrade(config, "base")
