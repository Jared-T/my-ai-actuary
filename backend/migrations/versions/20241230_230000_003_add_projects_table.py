"""Add projects table

Revision ID: 003
Revises: 002
Create Date: 2024-12-30 23:00:00.000000

Adds projects table for organizing work within engagements:
- Project metadata and identification
- Status and priority tracking
- Ownership and timeline management
- Project-level settings and configuration
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create projects table with enum types."""

    # Create enum types for project status and priority
    op.execute("""
        CREATE TYPE project_status AS ENUM (
            'draft', 'planning', 'active', 'on_hold',
            'completed', 'archived', 'cancelled'
        )
    """)
    op.execute("""
        CREATE TYPE project_priority AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)

    # Create projects table
    op.create_table(
        "projects",
        # Primary key
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Parent engagement reference
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False, comment="Parent engagement this project belongs to"),
        # Project identification
        sa.Column("name", sa.String(255), nullable=False, comment="Project name/title"),
        sa.Column("code", sa.String(50), nullable=True, comment="Short project code for reference (e.g., PROJ-001)"),
        sa.Column("description", sa.Text(), nullable=True, comment="Detailed project description"),
        # Status and priority
        sa.Column("status", postgresql.ENUM("draft", "planning", "active", "on_hold", "completed", "archived", "cancelled", name="project_status", create_type=False), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("priority", postgresql.ENUM("low", "medium", "high", "critical", name="project_priority", create_type=False), server_default=sa.text("'medium'"), nullable=False),
        # Ownership and responsibility
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True, comment="User responsible for the project (Supabase auth.users)"),
        # Timeline
        sa.Column("start_date", sa.Date(), nullable=True, comment="Planned or actual start date"),
        sa.Column("end_date", sa.Date(), nullable=True, comment="Planned or actual end date"),
        sa.Column("due_date", sa.Date(), nullable=True, comment="Project deadline"),
        # Effort tracking
        sa.Column("estimated_hours", sa.Integer(), nullable=True, comment="Estimated effort in hours"),
        sa.Column("actual_hours", sa.Integer(), nullable=True, comment="Actual effort spent in hours"),
        sa.Column("progress_percent", sa.Integer(), server_default=sa.text("0"), nullable=False, comment="Completion percentage (0-100)"),
        # Configuration and metadata
        sa.Column("settings", postgresql.JSONB(), nullable=True, comment="Project-level configuration settings"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional metadata: tags, custom fields, labels, etc."),
        # Audit fields (from AuditMixin)
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Soft delete fields (from SoftDeleteMixin)
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], name=op.f("fk_projects_engagement_id_engagements"), ondelete="CASCADE"),
        sa.UniqueConstraint("code", name=op.f("uq_projects_code")),
        sa.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name=op.f("ck_projects_progress_percent_range")),
    )

    # Create indexes for efficient querying
    op.create_index(op.f("ix_projects_engagement_id"), "projects", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_projects_code"), "projects", ["code"], unique=False)
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)
    op.create_index(op.f("ix_projects_priority"), "projects", ["priority"], unique=False)
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False)
    op.create_index(op.f("ix_projects_due_date"), "projects", ["due_date"], unique=False)
    op.create_index(op.f("ix_projects_created_at"), "projects", ["created_at"], unique=False)
    op.create_index(op.f("ix_projects_created_by"), "projects", ["created_by"], unique=False)
    op.create_index(op.f("ix_projects_is_deleted"), "projects", ["is_deleted"], unique=False)


def downgrade() -> None:
    """Drop projects table and enum types."""
    # Drop indexes first (in reverse order of creation)
    op.drop_index(op.f("ix_projects_is_deleted"), table_name="projects")
    op.drop_index(op.f("ix_projects_created_by"), table_name="projects")
    op.drop_index(op.f("ix_projects_created_at"), table_name="projects")
    op.drop_index(op.f("ix_projects_due_date"), table_name="projects")
    op.drop_index(op.f("ix_projects_owner_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_priority"), table_name="projects")
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_code"), table_name="projects")
    op.drop_index(op.f("ix_projects_engagement_id"), table_name="projects")

    # Drop the table
    op.drop_table("projects")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS project_priority")
    op.execute("DROP TYPE IF EXISTS project_status")
