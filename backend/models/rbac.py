"""
SQLAlchemy models for Role-Based Access Control (RBAC).

Provides models for:
- UserRole: Role assignments for users with optional scoping
- RoleAuditLog: Audit trail for role changes
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import TimestampMixin, UUIDMixin


class AppRole(str, Enum):
    """Application roles enum matching the database enum type."""
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class RoleScope(str, Enum):
    """Role scope enum matching the database enum type."""
    GLOBAL = "global"
    ENGAGEMENT = "engagement"
    PROJECT = "project"


class RoleAuditAction(str, Enum):
    """Role audit action enum matching the database enum type."""
    ASSIGNED = "assigned"
    REVOKED = "revoked"
    UPDATED = "updated"


# PostgreSQL ENUM types (must be created before using in columns)
app_role_enum = ENUM(
    "admin", "manager", "analyst", "reviewer",
    name="app_role",
    create_type=False,  # Created by migration
)

role_scope_enum = ENUM(
    "global", "engagement", "project",
    name="role_scope",
    create_type=False,  # Created by migration
)

role_audit_action_enum = ENUM(
    "assigned", "revoked", "updated",
    name="role_audit_action",
    create_type=False,  # Created by migration
)


class UserRole(UUIDMixin, TimestampMixin, Base):
    """
    User role assignment model.

    Stores role assignments for users with support for:
    - Global roles (apply to all resources)
    - Engagement-scoped roles (apply to specific engagement)
    - Project-scoped roles (apply to specific project)

    Attributes:
        id: Unique identifier
        user_id: The user being assigned the role
        role: The role being assigned
        scope: The scope of the role assignment
        engagement_id: Engagement ID if scope is 'engagement'
        project_id: Project ID if scope is 'project'
        granted_at: When the role was granted
        granted_by: User who granted this role
        expires_at: Optional expiration date for temporary roles
        is_active: Whether this role assignment is active
        notes: Optional notes about the role assignment
        created_at: When the record was created
        updated_at: When the record was last updated
    """

    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User ID from Supabase auth.users",
    )

    role: Mapped[AppRole] = mapped_column(
        app_role_enum,
        nullable=False,
        index=True,
        comment="The role assigned to the user",
    )

    scope: Mapped[RoleScope] = mapped_column(
        role_scope_enum,
        default=RoleScope.GLOBAL,
        server_default=text("'global'"),
        nullable=False,
        index=True,
        comment="Scope of the role assignment",
    )

    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Engagement ID if scope is 'engagement'",
    )

    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Project ID if scope is 'project'",
    )

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        comment="When the role was granted",
    )

    granted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="User who granted this role",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Optional expiration date for temporary roles",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
        index=True,
        comment="Whether this role assignment is active",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional notes about the role assignment",
    )

    # Relationships
    audit_logs: Mapped[list["RoleAuditLog"]] = relationship(
        "RoleAuditLog",
        back_populates="user_role",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return (
            f"<UserRole(id={self.id}, user_id={self.user_id}, "
            f"role={self.role.value}, scope={self.scope.value})>"
        )

    @property
    def is_expired(self) -> bool:
        """Check if this role assignment has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if this role assignment is currently valid (active and not expired)."""
        return self.is_active and not self.is_expired

    def revoke(self, revoked_by: UUID | None = None) -> None:
        """
        Revoke this role assignment.

        Args:
            revoked_by: The user revoking this role
        """
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)


class RoleAuditLog(UUIDMixin, Base):
    """
    Audit log for role changes.

    Tracks all changes to role assignments for security and compliance.

    Attributes:
        id: Unique identifier
        user_role_id: Reference to the user_roles entry
        user_id: User whose role was changed
        action: Type of role change
        role: The role that was changed
        previous_role: Previous role if this was an update
        scope: Scope of the role change
        engagement_id: Engagement ID if applicable
        project_id: Project ID if applicable
        performed_by: User who performed the action
        reason: Reason for the role change
        metadata: Additional context about the change
        created_at: When the change was made
    """

    __tablename__ = "role_audit_log"

    user_role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("user_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the user_roles entry",
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User whose role was changed",
    )

    action: Mapped[RoleAuditAction] = mapped_column(
        role_audit_action_enum,
        nullable=False,
        index=True,
        comment="Type of role change",
    )

    role: Mapped[AppRole] = mapped_column(
        app_role_enum,
        nullable=False,
        comment="The role that was changed",
    )

    previous_role: Mapped[AppRole | None] = mapped_column(
        app_role_enum,
        nullable=True,
        comment="Previous role if this was an update",
    )

    scope: Mapped[RoleScope] = mapped_column(
        role_scope_enum,
        nullable=False,
        comment="Scope of the role change",
    )

    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Engagement ID if applicable",
    )

    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Project ID if applicable",
    )

    performed_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="User who performed the action",
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for the role change",
    )

    metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional context about the change",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    user_role: Mapped["UserRole"] = relationship(
        "UserRole",
        back_populates="audit_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<RoleAuditLog(id={self.id}, user_id={self.user_id}, "
            f"action={self.action.value}, role={self.role.value})>"
        )
