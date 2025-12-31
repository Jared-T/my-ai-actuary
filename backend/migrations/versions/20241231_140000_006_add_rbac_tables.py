"""Add RBAC (Role-Based Access Control) tables

Revision ID: 006
Revises: 005
Create Date: 2024-12-31 14:00:00.000000

Adds tables for:
- user_roles: User role assignments with optional resource scoping
- role_audit_log: Audit trail for role changes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create RBAC tables."""

    # Create enum type for application roles
    op.execute("""
        CREATE TYPE app_role AS ENUM (
            'admin', 'manager', 'analyst', 'reviewer'
        )
    """)

    # Create enum type for role scope (where the role applies)
    op.execute("""
        CREATE TYPE role_scope AS ENUM (
            'global', 'engagement', 'project'
        )
    """)

    # Create enum type for role audit actions
    op.execute("""
        CREATE TYPE role_audit_action AS ENUM (
            'assigned', 'revoked', 'updated'
        )
    """)

    # Create user_roles table
    # This table stores role assignments for users
    # Roles can be global or scoped to specific engagements/projects
    op.create_table(
        "user_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User ID from Supabase auth.users",
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin", "manager", "analyst", "reviewer",
                name="app_role",
                create_type=False,
            ),
            nullable=False,
            comment="The role assigned to the user",
        ),
        sa.Column(
            "scope",
            postgresql.ENUM(
                "global", "engagement", "project",
                name="role_scope",
                create_type=False,
            ),
            server_default=sa.text("'global'"),
            nullable=False,
            comment="Scope of the role assignment",
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Engagement ID if scope is 'engagement'",
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Project ID if scope is 'project'",
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the role was granted",
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who granted this role",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Optional expiration date for temporary roles",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
            comment="Whether this role assignment is active",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Optional notes about the role assignment",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.CheckConstraint(
            "(scope = 'global' AND engagement_id IS NULL AND project_id IS NULL) OR "
            "(scope = 'engagement' AND engagement_id IS NOT NULL AND project_id IS NULL) OR "
            "(scope = 'project' AND project_id IS NOT NULL)",
            name=op.f("ck_user_roles_scope_consistency"),
        ),
    )

    # Create indexes for user_roles
    op.create_index(
        op.f("ix_user_roles_user_id"),
        "user_roles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_role"),
        "user_roles",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_scope"),
        "user_roles",
        ["scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_engagement_id"),
        "user_roles",
        ["engagement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_project_id"),
        "user_roles",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_is_active"),
        "user_roles",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_created_at"),
        "user_roles",
        ["created_at"],
        unique=False,
    )
    # Unique constraint: one active role per user per scope (prevents duplicate assignments)
    op.create_index(
        op.f("ix_user_roles_unique_active_global"),
        "user_roles",
        ["user_id", "role", "scope"],
        unique=True,
        postgresql_where=sa.text("is_active = true AND scope = 'global'"),
    )
    op.create_index(
        op.f("ix_user_roles_unique_active_engagement"),
        "user_roles",
        ["user_id", "role", "engagement_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true AND scope = 'engagement'"),
    )
    op.create_index(
        op.f("ix_user_roles_unique_active_project"),
        "user_roles",
        ["user_id", "role", "project_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true AND scope = 'project'"),
    )

    # Create role_audit_log table for tracking role changes
    op.create_table(
        "role_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to the user_roles entry",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User whose role was changed",
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                "assigned", "revoked", "updated",
                name="role_audit_action",
                create_type=False,
            ),
            nullable=False,
            comment="Type of role change",
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin", "manager", "analyst", "reviewer",
                name="app_role",
                create_type=False,
            ),
            nullable=False,
            comment="The role that was changed",
        ),
        sa.Column(
            "previous_role",
            postgresql.ENUM(
                "admin", "manager", "analyst", "reviewer",
                name="app_role",
                create_type=False,
            ),
            nullable=True,
            comment="Previous role if this was an update",
        ),
        sa.Column(
            "scope",
            postgresql.ENUM(
                "global", "engagement", "project",
                name="role_scope",
                create_type=False,
            ),
            nullable=False,
            comment="Scope of the role change",
        ),
        sa.Column(
            "engagement_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Engagement ID if applicable",
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Project ID if applicable",
        ),
        sa.Column(
            "performed_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User who performed the action",
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
            comment="Reason for the role change",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
            comment="Additional context about the change",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_audit_log")),
    )

    # Create indexes for role_audit_log
    op.create_index(
        op.f("ix_role_audit_log_user_role_id"),
        "role_audit_log",
        ["user_role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_audit_log_user_id"),
        "role_audit_log",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_audit_log_action"),
        "role_audit_log",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_audit_log_performed_by"),
        "role_audit_log",
        ["performed_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_audit_log_created_at"),
        "role_audit_log",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop RBAC tables."""
    op.drop_table("role_audit_log")
    op.drop_table("user_roles")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS role_audit_action")
    op.execute("DROP TYPE IF EXISTS role_scope")
    op.execute("DROP TYPE IF EXISTS app_role")
