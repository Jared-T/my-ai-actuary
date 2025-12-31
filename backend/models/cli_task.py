"""
CLI Task models for Codex CLI integration.

Provides models for tracking long-running CLI tasks including:
- Task submission and status tracking
- Batch processing job management
- External system call tracking and results
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SQLEnum,
    Float,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import AuditMixin, TraceableMixin, UUIDMixin


class CLITaskStatus(str, Enum):
    """Status of a CLI task."""

    PENDING = "pending"  # Task created but not yet started
    QUEUED = "queued"  # Task queued for execution
    IN_PROGRESS = "in_progress"  # Task currently executing
    COMPLETED = "completed"  # Task completed successfully
    FAILED = "failed"  # Task failed with error
    CANCELLED = "cancelled"  # Task was cancelled
    TIMEOUT = "timeout"  # Task exceeded timeout limit


class CLITaskType(str, Enum):
    """Types of CLI tasks that can be executed."""

    # Actuarial calculation tasks
    RESERVE_CALCULATION = "reserve_calculation"  # Chain ladder, BF, etc.
    IBNR_ESTIMATION = "ibnr_estimation"  # IBNR estimation models
    IFRS17_CALCULATION = "ifrs17_calculation"  # IFRS17 compliance calculations
    ALM_MODEL = "alm_model"  # Asset-liability modeling

    # Data processing tasks
    DATA_VALIDATION = "data_validation"  # Data quality checks
    DATA_TRANSFORMATION = "data_transformation"  # ETL operations
    BATCH_IMPORT = "batch_import"  # Bulk data import

    # Reporting tasks
    REPORT_GENERATION = "report_generation"  # Generate reports
    EXPORT_DATA = "export_data"  # Export data to external formats

    # Generic tasks
    SHELL_COMMAND = "shell_command"  # Execute shell commands
    CUSTOM_SCRIPT = "custom_script"  # Custom script execution


class CLITaskPriority(str, Enum):
    """Priority levels for task execution."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class CLITask(Base, UUIDMixin, AuditMixin, TraceableMixin):
    """
    CLI Task record for tracking long-running Codex CLI operations.

    Stores task metadata, execution state, progress, and results
    for audit and monitoring purposes.
    """

    __tablename__ = "cli_tasks"

    # Task identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable task name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed task description",
    )

    # Task classification
    task_type: Mapped[CLITaskType] = mapped_column(
        SQLEnum(CLITaskType, name="cli_task_type", create_constraint=True),
        nullable=False,
        index=True,
        comment="Type of CLI task",
    )

    status: Mapped[CLITaskStatus] = mapped_column(
        SQLEnum(CLITaskStatus, name="cli_task_status", create_constraint=True),
        default=CLITaskStatus.PENDING,
        server_default=text("'pending'"),
        nullable=False,
        index=True,
        comment="Current task status",
    )

    priority: Mapped[CLITaskPriority] = mapped_column(
        SQLEnum(CLITaskPriority, name="cli_task_priority", create_constraint=True),
        default=CLITaskPriority.NORMAL,
        server_default=text("'normal'"),
        nullable=False,
        index=True,
        comment="Task execution priority",
    )

    # Command and execution details
    command: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="CLI command to execute",
    )

    working_directory: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Working directory for command execution",
    )

    environment_vars: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Environment variables for execution",
    )

    # Input/Output
    input_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Input parameters and data for the task",
    )

    output_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Output results from task execution",
    )

    # File references
    input_file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Path to input file if applicable",
    )

    output_file_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Path to output file/artefact",
    )

    # Progress tracking
    progress_percentage: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        nullable=False,
        comment="Task completion percentage (0-100)",
    )

    progress_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Current progress status message",
    )

    # Timing information
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task was queued",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task execution started",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task completed",
    )

    # Timeout configuration
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        default=3600,
        server_default=text("3600"),
        nullable=False,
        comment="Maximum execution time in seconds",
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if task failed",
    )

    error_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Detailed error information",
    )

    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Process exit code",
    )

    # Process information
    process_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Operating system process ID",
    )

    # Resource usage
    memory_used_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Peak memory usage in bytes",
    )

    cpu_time_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Total CPU time used",
    )

    # Retry handling
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
        comment="Number of retry attempts",
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        server_default=text("3"),
        nullable=False,
        comment="Maximum allowed retry attempts",
    )

    # Parent task reference (for batch operations)
    parent_task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Parent task ID for batch operations",
    )

    # Engagement association
    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Associated engagement ID",
    )

    # Metadata for additional context
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        name="metadata",
        comment="Additional task metadata",
    )

    def __repr__(self) -> str:
        return (
            f"<CLITask(id={self.id}, name='{self.name}', "
            f"type={self.task_type.value}, status={self.status.value})>"
        )

    def queue(self) -> None:
        """Mark task as queued for execution."""
        self.status = CLITaskStatus.QUEUED
        self.queued_at = datetime.now(timezone.utc)

    def start(self, process_id: int | None = None) -> None:
        """Mark task as started."""
        self.status = CLITaskStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)
        self.process_id = process_id
        self.progress_percentage = 0.0

    def update_progress(
        self,
        percentage: float,
        message: str | None = None,
    ) -> None:
        """Update task progress."""
        self.progress_percentage = min(max(percentage, 0.0), 100.0)
        if message:
            self.progress_message = message

    def complete(
        self,
        output_data: dict[str, Any] | None = None,
        output_file_path: str | None = None,
        exit_code: int = 0,
    ) -> None:
        """Mark task as completed successfully."""
        self.status = CLITaskStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.progress_percentage = 100.0
        self.exit_code = exit_code
        if output_data:
            self.output_data = output_data
        if output_file_path:
            self.output_file_path = output_file_path

    def fail(
        self,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Mark task as failed."""
        self.status = CLITaskStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        if exit_code is not None:
            self.exit_code = exit_code

    def timeout(self) -> None:
        """Mark task as timed out."""
        self.status = CLITaskStatus.TIMEOUT
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = f"Task exceeded timeout limit of {self.timeout_seconds} seconds"

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the task."""
        self.status = CLITaskStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        if reason:
            self.error_message = f"Cancelled: {reason}"

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status in (CLITaskStatus.FAILED, CLITaskStatus.TIMEOUT)
            and (self.retry_count or 0) < (self.max_retries or 3)
        )

    def prepare_retry(self) -> None:
        """Prepare task for retry."""
        if not self.can_retry():
            raise ValueError("Task cannot be retried")

        self.retry_count += 1
        self.status = CLITaskStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.error_details = None
        self.exit_code = None
        self.progress_percentage = 0.0
        self.progress_message = None

    @property
    def duration_seconds(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status in (CLITaskStatus.QUEUED, CLITaskStatus.IN_PROGRESS)

    @property
    def is_finished(self) -> bool:
        """Check if task has finished (success or failure)."""
        return self.status in (
            CLITaskStatus.COMPLETED,
            CLITaskStatus.FAILED,
            CLITaskStatus.CANCELLED,
            CLITaskStatus.TIMEOUT,
        )
