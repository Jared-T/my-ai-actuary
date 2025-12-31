"""
Backup and recovery models for critical data protection.

Provides models for tracking:
- Backup jobs and their status
- Backup metadata and locations
- Recovery operations and audit trails
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import AuditMixin, UUIDMixin


class BackupStatus(str, Enum):
    """Status of a backup operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class BackupType(str, Enum):
    """Types of backup operations."""

    FULL = "full"  # Complete database backup
    INCREMENTAL = "incremental"  # Changes since last backup
    DIFFERENTIAL = "differential"  # Changes since last full backup
    AUDIT_LOGS = "audit_logs"  # Audit trail only
    ARTEFACTS = "artefacts"  # File artefacts only
    ENGAGEMENT = "engagement"  # Single engagement backup


class RecoveryStatus(str, Enum):
    """Status of a recovery operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Backup(Base, UUIDMixin, AuditMixin):
    """
    Backup job record for tracking backup operations.

    Stores metadata about each backup including location, size,
    and status for audit and recovery purposes.
    """

    __tablename__ = "backups"

    # Backup identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable backup name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of backup purpose",
    )

    # Backup type and status
    backup_type: Mapped[BackupType] = mapped_column(
        SQLEnum(BackupType, name="backup_type", create_constraint=True),
        nullable=False,
        index=True,
    )

    status: Mapped[BackupStatus] = mapped_column(
        SQLEnum(BackupStatus, name="backup_status", create_constraint=True),
        default=BackupStatus.PENDING,
        server_default=text("'pending'"),
        nullable=False,
        index=True,
    )

    # Storage information
    storage_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Path or URL to backup storage location",
    )

    storage_provider: Mapped[str] = mapped_column(
        String(50),
        default="local",
        server_default=text("'local'"),
        nullable=False,
        comment="Storage provider: local, supabase, s3, etc.",
    )

    # Backup metrics
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Total size of backup in bytes",
    )

    record_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of records included in backup",
    )

    # Timing information
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When backup started",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When backup completed",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When backup should be cleaned up",
    )

    # Backup content metadata
    tables_included: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of tables included in backup",
    )

    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Specific engagement if engagement-level backup",
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if backup failed",
    )

    # Checksum for integrity verification
    checksum: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="SHA-256 checksum of backup file",
    )

    # Metadata for additional context
    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional backup metadata",
    )

    def __repr__(self) -> str:
        return (
            f"<Backup(id={self.id}, name='{self.name}', "
            f"type={self.backup_type.value}, status={self.status.value})>"
        )

    def start(self) -> None:
        """Mark backup as started."""
        self.status = BackupStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)

    def complete(
        self,
        storage_path: str,
        file_size_bytes: int,
        record_count: int,
        checksum: str,
    ) -> None:
        """Mark backup as completed with results."""
        self.status = BackupStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.storage_path = storage_path
        self.file_size_bytes = file_size_bytes
        self.record_count = record_count
        self.checksum = checksum

    def fail(self, error_message: str) -> None:
        """Mark backup as failed with error."""
        self.status = BackupStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message


class Recovery(Base, UUIDMixin, AuditMixin):
    """
    Recovery operation record for tracking restore operations.

    Maintains audit trail of all recovery attempts including
    source backup, target state, and operation results.
    """

    __tablename__ = "recoveries"

    # Recovery identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable recovery name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of recovery purpose",
    )

    # Source backup reference
    backup_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Source backup for recovery",
    )

    # Recovery status
    status: Mapped[RecoveryStatus] = mapped_column(
        SQLEnum(RecoveryStatus, name="recovery_status", create_constraint=True),
        default=RecoveryStatus.PENDING,
        server_default=text("'pending'"),
        nullable=False,
        index=True,
    )

    # Timing information
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recovery started",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When recovery completed",
    )

    # Recovery scope
    tables_recovered: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Tables that were recovered",
    )

    records_recovered: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of records recovered",
    )

    # Target engagement (if specific)
    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Target engagement for selective recovery",
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if recovery failed",
    )

    # Recovery options
    options: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Recovery options: overwrite, merge, etc.",
    )

    # Pre-recovery state snapshot (for rollback)
    pre_recovery_snapshot: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Path to pre-recovery state snapshot",
    )

    # Metadata for additional context
    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional recovery metadata",
    )

    def __repr__(self) -> str:
        return (
            f"<Recovery(id={self.id}, name='{self.name}', "
            f"backup_id={self.backup_id}, status={self.status.value})>"
        )

    def start(self) -> None:
        """Mark recovery as started."""
        self.status = RecoveryStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)

    def complete(self, tables_recovered: list[str], records_recovered: int) -> None:
        """Mark recovery as completed."""
        self.status = RecoveryStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.tables_recovered = tables_recovered
        self.records_recovered = records_recovered

    def fail(self, error_message: str) -> None:
        """Mark recovery as failed."""
        self.status = RecoveryStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message

    def rollback(self) -> None:
        """Mark recovery as rolled back."""
        self.status = RecoveryStatus.ROLLED_BACK
        self.completed_at = datetime.now(timezone.utc)
