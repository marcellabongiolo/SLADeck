"""Create core multi-tenant domain tables.

Revision ID: 0001_core_domain
Revises:
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_core_domain"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


membership_role = sa.Enum("owner", "admin", "manager", "member", name="membership_role")
request_status = sa.Enum(
    "open",
    "in_progress",
    "waiting",
    "resolved",
    "closed",
    name="request_status",
)
request_priority = sa.Enum("low", "normal", "high", "urgent", name="request_priority")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role", membership_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_membership_user_org",
        ),
    )
    op.create_index(
        "ix_memberships_organization_role",
        "memberships",
        ["organization_id", "role"],
        unique=False,
    )

    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("first_response_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "name",
            name="uq_sla_policy_org_name",
        ),
    )
    op.create_index(
        "ix_sla_policies_organization_id",
        "sla_policies",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", request_status, nullable=False),
        sa.Column("priority", request_priority, nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("sla_policy_id", sa.Uuid(), nullable=True),
        sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_requests_assignee_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id", "organization_id"],
            ["memberships.user_id", "memberships.organization_id"],
            name="fk_requests_requester_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sla_policy_id"],
            ["sla_policies.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_requests_org_assignee",
        "requests",
        ["organization_id", "assignee_id"],
        unique=False,
    )
    op.create_index(
        "ix_requests_org_priority",
        "requests",
        ["organization_id", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_requests_org_status",
        "requests",
        ["organization_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_requests_org_status", table_name="requests")
    op.drop_index("ix_requests_org_priority", table_name="requests")
    op.drop_index("ix_requests_org_assignee", table_name="requests")
    op.drop_table("requests")

    op.drop_index("ix_sla_policies_organization_id", table_name="sla_policies")
    op.drop_table("sla_policies")

    op.drop_index("ix_memberships_organization_role", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    request_priority.drop(op.get_bind(), checkfirst=True)
    request_status.drop(op.get_bind(), checkfirst=True)
    membership_role.drop(op.get_bind(), checkfirst=True)
