"""Add backup and recovery tables

Revision ID: 002
Revises: 001
Create Date: 2024-12-30 22:00:00.000000

Adds tables for:
- Backups: tracking backup operations
- Recoveries: tracking recovery operations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create backup and recovery tables."""

    # Create enum types for backup and recovery
    op.execute("""
        CREATE TYPE backup_type AS ENUM (
            'full', 'incremental', 'differential',
            'audit_logs', 'artefacts', 'engagement'
        )
    """)
    op.execute("""
        CREATE TYPE backup_status AS ENUM (
            'pending', 'in_progress', 'completed',
            'failed', 'cancelled', 'expired'
        )
    """)
    op.execute("""
        CREATE TYPE recovery_status AS ENUM (
            'pending', 'in_progress', 'completed',
            'failed', 'rolled_back'
        )
    """)

    # Create backups table
    op.create_table(
        "backups",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, comment="Human-readable backup name"),
        sa.Column("description", sa.Text(), nullable=True, comment="Optional description of backup purpose"),
        sa.Column("backup_type", postgresql.ENUM("full", "incremental", "differential", "audit_logs", "artefacts", "engagement", name="backup_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "in_progress", "completed", "failed", "cancelled", "expired", name="backup_status", create_type=False), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=True, comment="Path or URL to backup storage location"),
        sa.Column("storage_provider", sa.String(50), server_default=sa.text("'local'"), nullable=False, comment="Storage provider: local, supabase, s3, etc."),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True, comment="Total size of backup in bytes"),
        sa.Column("record_count", sa.Integer(), nullable=True, comment="Number of records included in backup"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="When backup started"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="When backup completed"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, comment="When backup should be cleaned up"),
        sa.Column("tables_included", postgresql.JSONB(), nullable=True, comment="List of tables included in backup"),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Specific engagement if engagement-level backup"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message if backup failed"),
        sa.Column("checksum", sa.String(128), nullable=True, comment="SHA-256 checksum of backup file"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional backup metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backups")),
    )
    op.create_index(op.f("ix_backups_backup_type"), "backups", ["backup_type"], unique=False)
    op.create_index(op.f("ix_backups_created_at"), "backups", ["created_at"], unique=False)
    op.create_index(op.f("ix_backups_created_by"), "backups", ["created_by"], unique=False)
    op.create_index(op.f("ix_backups_engagement_id"), "backups", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_backups_expires_at"), "backups", ["expires_at"], unique=False)
    op.create_index(op.f("ix_backups_status"), "backups", ["status"], unique=False)

    # Create recoveries table
    op.create_table(
        "recoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, comment="Human-readable recovery name"),
        sa.Column("description", sa.Text(), nullable=True, comment="Description of recovery purpose"),
        sa.Column("backup_id", postgresql.UUID(as_uuid=True), nullable=False, comment="Source backup for recovery"),
        sa.Column("status", postgresql.ENUM("pending", "in_progress", "completed", "failed", "rolled_back", name="recovery_status", create_type=False), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="When recovery started"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True, comment="When recovery completed"),
        sa.Column("tables_recovered", postgresql.JSONB(), nullable=True, comment="Tables that were recovered"),
        sa.Column("records_recovered", sa.Integer(), nullable=True, comment="Number of records recovered"),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Target engagement for selective recovery"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message if recovery failed"),
        sa.Column("options", postgresql.JSONB(), nullable=True, comment="Recovery options: overwrite, merge, etc."),
        sa.Column("pre_recovery_snapshot", sa.String(1024), nullable=True, comment="Path to pre-recovery state snapshot"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional recovery metadata"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recoveries")),
    )
    op.create_index(op.f("ix_recoveries_backup_id"), "recoveries", ["backup_id"], unique=False)
    op.create_index(op.f("ix_recoveries_created_at"), "recoveries", ["created_at"], unique=False)
    op.create_index(op.f("ix_recoveries_created_by"), "recoveries", ["created_by"], unique=False)
    op.create_index(op.f("ix_recoveries_engagement_id"), "recoveries", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_recoveries_status"), "recoveries", ["status"], unique=False)


def downgrade() -> None:
    """Drop backup and recovery tables."""
    op.drop_table("recoveries")
    op.drop_table("backups")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS recovery_status")
    op.execute("DROP TYPE IF EXISTS backup_status")
    op.execute("DROP TYPE IF EXISTS backup_type")
