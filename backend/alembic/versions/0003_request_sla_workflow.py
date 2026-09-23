"""Add request response tracking and tenant-safe SLA policy relation.

Revision ID: 0003_request_sla_workflow
Revises: 0002_auth_sessions
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_request_sla_workflow"
down_revision: str | None = "0002_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_sla_policy_id_org",
        "sla_policies",
        ["id", "organization_id"],
    )
    op.drop_constraint(
        "requests_sla_policy_id_fkey",
        "requests",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_requests_sla_policy_org",
        "requests",
        "sla_policies",
        ["sla_policy_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_requests_sla_policy_org",
        "requests",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "requests_sla_policy_id_fkey",
        "requests",
        "sla_policies",
        ["sla_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_sla_policy_id_org", "sla_policies", type_="unique")
    op.drop_column("requests", "first_responded_at")
