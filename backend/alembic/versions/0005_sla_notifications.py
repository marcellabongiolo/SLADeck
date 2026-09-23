"""Add durable SLA notification records.

Revision ID: 0005_sla_notifications
Revises: 0004_comments_audit
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_sla_notifications"
down_revision: str | None = "0004_comments_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sla_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
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
            name="fk_sla_notifications_request_org",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            "stage",
            "kind",
            name="uq_sla_notification_request_stage_kind",
        ),
    )
    op.create_index(
        "ix_sla_notifications_request_created",
        "sla_notifications",
        ["request_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_sla_notifications_org_created",
        "sla_notifications",
        ["organization_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sla_notifications_org_created", table_name="sla_notifications")
    op.drop_index("ix_sla_notifications_request_created", table_name="sla_notifications")
    op.drop_table("sla_notifications")
