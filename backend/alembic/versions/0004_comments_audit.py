"""Add comments and immutable request audit trail.

Revision ID: 0004_comments_audit
Revises: 0003_request_sla_workflow
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_comments_audit"
down_revision: str | None = "0003_request_sla_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_request_id_org",
        "requests",
        ["id", "organization_id"],
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id", "organization_id"],
            ["requests.id", "requests.organization_id"],
            name="fk_comments_request_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_comments_author_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_comments_request_created",
        "comments",
        ["request_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id", "organization_id"],
            ["requests.id", "requests.organization_id"],
            name="fk_audit_events_request_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_request_created",
        "audit_events",
        ["request_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_org_type",
        "audit_events",
        ["organization_id", "event_type"],
        unique=False,
    )

    op.execute(
        """
        CREATE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")

    op.drop_index("ix_audit_events_org_type", table_name="audit_events")
    op.drop_index("ix_audit_events_request_created", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_comments_request_created", table_name="comments")
    op.drop_table("comments")

    op.drop_constraint("uq_request_id_org", "requests", type_="unique")
