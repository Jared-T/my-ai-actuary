"""
Workflow run models for tracking actuarial process execution.

Workflow runs represent the execution of actuarial processes within
an engagement. They track status, timing, and link to generated artefacts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, TraceableMixin, UUIDMixin

if TYPE_CHECKING:
    from models.artefact import Artefact
    from models.engagement import Engagement


class WorkflowType(str, Enum):
    """Types of actuarial workflows."""

    # Data workflows
    DATA_INGESTION = "data_ingestion"
    DATA_VALIDATION = "data_validation"
    DATA_TRANSFORMATION = "data_transformation"

    # Reserving workflows
    RESERVE_CALCULATION = "reserve_calculation"
    TRIANGLE_ANALYSIS = "triangle_analysis"
    IBNR_ESTIMATION = "ibnr_estimation"

    # IFRS17 workflows
    IFRS17_MEASUREMENT = "ifrs17_measurement"
    CSM_CALCULATION = "csm_calculation"
    COHORT_GROUPING = "cohort_grouping"

    # ALM workflows
    ALM_ANALYSIS = "alm_analysis"
    CASHFLOW_PROJECTION = "cashflow_projection"
    DURATION_MATCHING = "duration_matching"

    # Reinsurance workflows
    REINSURANCE_ANALYSIS = "reinsurance_analysis"
    TREATY_CALCULATION = "treaty_calculation"
    RECOVERIES_CALCULATION = "recoveries_calculation"

    # Reporting workflows
    REPORT_GENERATION = "report_generation"
    DASHBOARD_UPDATE = "dashboard_update"

    # Review workflows
    QUALITY_CHECK = "quality_check"
    PEER_REVIEW = "peer_review"
    SIGN_OFF = "sign_off"

    # General
    CUSTOM = "custom"


class WorkflowStatus(str, Enum):
    """Execution status of a workflow run."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowRun(Base, UUIDMixin, AuditMixin, SoftDeleteMixin, TraceableMixin):
    """
    Execution record for an actuarial workflow.

    Tracks the full lifecycle of a workflow execution, including timing,
    status, inputs, outputs, and any errors encountered.
    """

    __tablename__ = "workflow_runs"

    # Engagement association
    engagement_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Workflow identification
    workflow_type: Mapped[WorkflowType] = mapped_column(
        SQLEnum(WorkflowType, name="workflow_type", create_constraint=True),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Descriptive name for this workflow run",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Period for the workflow (e.g., "2024-Q4", "2024-12")
    period: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Reporting/valuation period",
    )

    # Execution status
    status: Mapped[WorkflowStatus] = mapped_column(
        SQLEnum(WorkflowStatus, name="workflow_status", create_constraint=True),
        default=WorkflowStatus.PENDING,
        server_default=text("'pending'"),
        nullable=False,
        index=True,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Execution details
    step_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of steps in the workflow",
    )

    current_step: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current step being executed",
    )

    # Input parameters
    input_params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Input parameters for the workflow",
    )

    # Output summary
    output_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Summary of workflow outputs and results",
    )

    # Error information
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if workflow failed",
    )

    error_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Detailed error information including stack trace",
    )

    # Agent execution info
    agent_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Name of the agent that executed this workflow",
    )

    # Performance metrics
    metrics: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Execution metrics: duration, tokens, api calls, etc.",
    )

    # Relationships
    # Note: Use lazy="raise" to prevent accidental N+1 queries.
    # Explicitly load relationships when needed using selectinload() or joinedload()
    engagement: Mapped["Engagement"] = relationship(
        "Engagement",
        back_populates="workflow_runs",
        lazy="raise",  # Require explicit loading
    )

    artefacts: Mapped[list["Artefact"]] = relationship(
        "Artefact",
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowRun(id={self.id}, type={self.workflow_type.value}, "
            f"status={self.status.value}, period={self.period})>"
        )

    @property
    def duration_seconds(self) -> float | None:
        """Calculate workflow execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def progress_percent(self) -> float:
        """Calculate workflow progress as a percentage (0-100).

        Returns a value clamped between 0 and 100 to handle edge cases
        where current_step might exceed step_count.
        """
        if self.step_count == 0:
            return 0.0
        progress = (self.current_step / self.step_count) * 100
        return max(0.0, min(100.0, progress))  # Clamp between 0 and 100

    def start(self) -> None:
        """Mark workflow as started."""
        if self.status not in (WorkflowStatus.PENDING, WorkflowStatus.QUEUED):
            raise ValueError(f"Cannot start workflow in {self.status.value} status")
        self.status = WorkflowStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, output_summary: dict | None = None) -> None:
        """Mark workflow as completed."""
        if self.status != WorkflowStatus.RUNNING:
            raise ValueError(f"Cannot complete workflow in {self.status.value} status")
        self.status = WorkflowStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        if output_summary:
            self.output_summary = output_summary

    def fail(self, error_message: str, error_details: dict | None = None) -> None:
        """Mark workflow as failed with error information."""
        self.status = WorkflowStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message
        self.error_details = error_details

    def cancel(self) -> None:
        """Cancel a pending or running workflow."""
        if self.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            raise ValueError(f"Cannot cancel workflow in {self.status.value} status")
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
