"""
Audit trail models for comprehensive activity logging.

Provides immutable audit records for all significant actions in the system.
Critical for compliance with actuarial professional standards and regulations.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import TraceableMixin, UUIDMixin


class AuditAction(str, Enum):
    """Categories of auditable actions."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"

    # Session actions
    SESSION_CREATE = "session_create"
    SESSION_DELETE = "session_delete"

    # Engagement actions
    ENGAGEMENT_CREATE = "engagement_create"
    ENGAGEMENT_UPDATE = "engagement_update"
    ENGAGEMENT_DELETE = "engagement_delete"
    ENGAGEMENT_ARCHIVE = "engagement_archive"

    # Workflow actions
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_FAIL = "workflow_fail"
    WORKFLOW_CANCEL = "workflow_cancel"

    # Artefact actions
    ARTEFACT_CREATE = "artefact_create"
    ARTEFACT_ACCESS = "artefact_access"
    ARTEFACT_DELETE = "artefact_delete"
    ARTEFACT_VERIFY = "artefact_verify"
    ARTEFACT_HASH_MISMATCH = "artefact_hash_mismatch"
    ARTEFACT_VERSION = "artefact_version"

    # Approval actions
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_APPROVE = "approval_approve"
    APPROVAL_REJECT = "approval_reject"
    APPROVAL_REVOKE = "approval_revoke"

    # Agent actions
    AGENT_INVOKE = "agent_invoke"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"

    # Data access
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"

    # Administrative
    SETTINGS_CHANGE = "settings_change"
    PERMISSION_CHANGE = "permission_change"

    # Compliance actions
    COMPLIANCE_REPORT_GENERATE = "compliance_report_generate"
    COMPLIANCE_REPORT_EXPORT = "compliance_report_export"
    COMPLIANCE_CHECK = "compliance_check"
    COMPLIANCE_VIOLATION = "compliance_violation"

    # Cryptographic verification
    HASH_GENERATE = "hash_generate"
    HASH_VERIFY = "hash_verify"
    SIGNATURE_CREATE = "signature_create"
    SIGNATURE_VERIFY = "signature_verify"

    # System operations
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_RESTORE = "system_restore"
    AUDIT_EXPORT = "audit_export"
    AUDIT_ARCHIVE = "audit_archive"


class AuditSeverity(str, Enum):
    """Severity level for audit events."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base, UUIDMixin, TraceableMixin):
    """
    Immutable audit log record for tracking all significant system actions.

    Records are append-only and should never be modified or deleted.
    Provides comprehensive audit trail for compliance and debugging.
    """

    __tablename__ = "audit_logs"

    # Actor information
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who performed the action (null for system actions)",
    )

    # Action details
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, name="audit_action", create_constraint=True),
        nullable=False,
        index=True,
    )

    severity: Mapped[AuditSeverity] = mapped_column(
        SQLEnum(AuditSeverity, name="audit_severity", create_constraint=True),
        default=AuditSeverity.INFO,
        server_default=text("'info'"),
        nullable=False,
        index=True,
    )

    # Target resource
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of resource acted upon (e.g., 'engagement', 'workflow')",
    )

    resource_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID of the resource acted upon",
    )

    # Description and context
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable description of the action",
    )

    # Before/after state for changes
    old_value: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous state before the action",
    )

    new_value: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="New state after the action",
    )

    # Additional metadata
    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional context: agent name, model, tokens, etc.",
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="Client IP address",
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Client user agent string",
    )

    # Timestamp (immutable - no updated_at)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Session and engagement context
    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Session where the action occurred",
    )

    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Engagement context for the action",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action.value}, "
            f"resource={self.resource_type}/{self.resource_id})>"
        )

    @classmethod
    def create(
        cls,
        action: AuditAction,
        resource_type: str,
        description: str,
        user_id: UUID | None = None,
        resource_id: UUID | None = None,
        old_value: dict | None = None,
        new_value: dict | None = None,
        metadata: dict | None = None,
        trace_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: UUID | None = None,
        engagement_id: UUID | None = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> "AuditLog":
        """
        Factory method for creating audit log entries.

        Provides a clean interface for creating audit records with all
        required and optional fields properly initialized.
        """
        return cls(
            user_id=user_id,
            action=action,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            engagement_id=engagement_id,
        )
