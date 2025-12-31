"""
Engagement models for client project management.

An engagement represents a client project or assignment that may contain
multiple workflow runs, artefacts, and require various approvals.
"""

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum as SQLEnum, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from models.artefact import Artefact
    from models.approval import Approval
    from models.project import Project
    from models.session import Session
    from models.workflow import WorkflowRun


class EngagementStatus(str, Enum):
    """Status of an engagement."""

    DRAFT = "draft"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class EngagementType(str, Enum):
    """Type of actuarial engagement."""

    RESERVING = "reserving"
    IFRS17 = "ifrs17"
    ALM = "alm"
    REINSURANCE = "reinsurance"
    PRICING = "pricing"
    VALUATION = "valuation"
    REVIEW = "review"
    ADVISORY = "advisory"
    OTHER = "other"


class Engagement(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Client engagement representing an actuarial project or assignment.

    Engagements are the primary organizational unit for actuarial work.
    They contain workflow runs, generate artefacts, and require approvals.
    """

    __tablename__ = "engagements"

    # Client information
    client_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Client identifier code",
    )

    client_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full client name",
    )

    # Engagement details
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Engagement name/title",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed engagement description",
    )

    engagement_type: Mapped[EngagementType] = mapped_column(
        SQLEnum(EngagementType, name="engagement_type", create_constraint=True),
        default=EngagementType.OTHER,
        nullable=False,
        index=True,
    )

    status: Mapped[EngagementStatus] = mapped_column(
        SQLEnum(EngagementStatus, name="engagement_status", create_constraint=True),
        default=EngagementStatus.DRAFT,
        server_default=text("'draft'"),
        nullable=False,
        index=True,
    )

    # Engagement period
    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Start of the reporting/valuation period",
    )

    period_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="End of the reporting/valuation period",
    )

    # Deadlines
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Engagement delivery deadline",
    )

    # Team and responsibility
    lead_actuary_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Lead actuary responsible for the engagement",
    )

    reviewer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Peer reviewer for the engagement",
    )

    # Configuration and metadata
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Engagement-specific configuration and settings",
    )

    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional metadata: tags, custom fields, etc.",
    )

    # Relationships
    # Note: Use lazy="raise" to prevent accidental N+1 queries.
    # Explicitly load relationships when needed using selectinload() or joinedload()
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="engagement",
        lazy="raise",  # Require explicit loading
    )

    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(
        "WorkflowRun",
        back_populates="engagement",
        cascade="all, delete-orphan",
        lazy="raise",  # Require explicit loading
    )

    artefacts: Mapped[list["Artefact"]] = relationship(
        "Artefact",
        back_populates="engagement",
        lazy="raise",  # Require explicit loading
    )

    approvals: Mapped[list["Approval"]] = relationship(
        "Approval",
        back_populates="engagement",
        lazy="raise",  # Require explicit loading
    )

    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="engagement",
        cascade="all, delete-orphan",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        return (
            f"<Engagement(id={self.id}, client={self.client_code}, "
            f"name={self.name!r}, status={self.status.value})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if the engagement is in an active state."""
        return self.status == EngagementStatus.ACTIVE

    @property
    def is_editable(self) -> bool:
        """Check if the engagement can be modified."""
        return self.status in (EngagementStatus.DRAFT, EngagementStatus.ACTIVE)

    def activate(self) -> None:
        """Transition engagement to active status."""
        if self.status not in (EngagementStatus.DRAFT, EngagementStatus.ON_HOLD):
            raise ValueError(f"Cannot activate engagement in {self.status.value} status")
        self.status = EngagementStatus.ACTIVE

    def complete(self) -> None:
        """Mark engagement as completed."""
        if self.status != EngagementStatus.ACTIVE:
            raise ValueError(f"Cannot complete engagement in {self.status.value} status")
        self.status = EngagementStatus.COMPLETED

    def archive(self) -> None:
        """Archive a completed engagement."""
        if self.status not in (EngagementStatus.COMPLETED, EngagementStatus.CANCELLED):
            raise ValueError(f"Cannot archive engagement in {self.status.value} status")
        self.status = EngagementStatus.ARCHIVED
