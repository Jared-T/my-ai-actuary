"""
Approval models for professional sign-off workflows.

Implements the approval gate system required by actuarial professional
standards. All significant outputs require documented professional approval.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import TraceableMixin, UUIDMixin

if TYPE_CHECKING:
    from models.artefact import Artefact
    from models.engagement import Engagement


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApprovalType(str, Enum):
    """Type of approval being requested."""

    # Work product approvals
    ARTEFACT_REVIEW = "artefact_review"
    REPORT_SIGN_OFF = "report_sign_off"
    DATA_VALIDATION = "data_validation"

    # Process approvals
    WORKFLOW_APPROVAL = "workflow_approval"
    METHODOLOGY_APPROVAL = "methodology_approval"

    # Professional sign-offs
    ACTUARIAL_SIGN_OFF = "actuarial_sign_off"
    PEER_REVIEW = "peer_review"
    FINAL_SIGN_OFF = "final_sign_off"

    # Administrative
    RELEASE_APPROVAL = "release_approval"
    EXCEPTION_APPROVAL = "exception_approval"


class Approval(Base, UUIDMixin, TraceableMixin):
    """
    Professional approval record for artefacts and work products.

    Tracks the full approval lifecycle including request, review,
    decision, and any subsequent revocation. Provides the audit
    trail required for actuarial professional standards.
    """

    __tablename__ = "approvals"

    # Target associations (one of these should be set)
    artefact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("artefacts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Approval type
    approval_type: Mapped[ApprovalType] = mapped_column(
        SQLEnum(ApprovalType, name="approval_type", create_constraint=True),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus, name="approval_status", create_constraint=True),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Requestor
    requested_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User who requested the approval",
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    request_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from the requestor",
    )

    # Approver
    approver_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who approved/rejected",
    )

    # Designated approver (if specific person is required)
    designated_approver_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Specific user designated to approve (if applicable)",
    )

    # Decision timing
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Expiration (some approvals may have time limits)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Decision notes
    decision_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notes from the approver explaining the decision",
    )

    # Rejection reason (structured)
    rejection_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Standardized rejection reason code",
    )

    # Revocation info
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    revoked_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )

    revocation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional metadata
    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional approval context and metadata",
    )

    # Professional qualifications at time of approval
    approver_qualifications: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Approver's professional qualifications at decision time",
    )

    # Relationships
    # Note: Use lazy="raise" to prevent accidental N+1 queries.
    # Explicitly load relationships when needed using selectinload() or joinedload()
    artefact: Mapped["Artefact | None"] = relationship(
        "Artefact",
        back_populates="approvals",
        lazy="raise",  # Require explicit loading
    )

    engagement: Mapped["Engagement | None"] = relationship(
        "Engagement",
        back_populates="approvals",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        return (
            f"<Approval(id={self.id}, type={self.approval_type.value}, "
            f"status={self.status.value})>"
        )

    @property
    def is_pending(self) -> bool:
        """Check if approval is still pending."""
        return self.status == ApprovalStatus.PENDING

    @property
    def is_approved(self) -> bool:
        """Check if approval was granted."""
        return self.status == ApprovalStatus.APPROVED

    @property
    def is_expired(self) -> bool:
        """Check if approval has expired."""
        if self.status == ApprovalStatus.EXPIRED:
            return True
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return True
        return False

    def approve(
        self,
        approver_id: UUID,
        notes: str | None = None,
        qualifications: dict | None = None,
    ) -> None:
        """Grant approval."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve in {self.status.value} status")

        self.status = ApprovalStatus.APPROVED
        self.approver_id = approver_id
        self.reviewed_at = datetime.now(timezone.utc)
        self.decision_notes = notes
        self.approver_qualifications = qualifications

    def reject(
        self,
        approver_id: UUID,
        reason: str,
        notes: str | None = None,
    ) -> None:
        """Reject the approval request."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject in {self.status.value} status")

        self.status = ApprovalStatus.REJECTED
        self.approver_id = approver_id
        self.reviewed_at = datetime.now(timezone.utc)
        self.rejection_reason = reason
        self.decision_notes = notes

    def revoke(
        self,
        revoked_by_id: UUID,
        reason: str,
    ) -> None:
        """Revoke a previously granted approval."""
        if self.status != ApprovalStatus.APPROVED:
            raise ValueError(f"Cannot revoke in {self.status.value} status")

        self.status = ApprovalStatus.REVOKED
        self.revoked_at = datetime.now(timezone.utc)
        self.revoked_by = revoked_by_id
        self.revocation_reason = reason

    def mark_expired(self) -> None:
        """Mark the approval as expired."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot expire in {self.status.value} status")
        self.status = ApprovalStatus.EXPIRED
