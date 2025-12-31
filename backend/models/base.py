"""
Base model mixins providing common functionality for all models.

Provides reusable mixins for:
- UUID primary keys
- Timestamps (created_at, updated_at)
- Audit tracking (created_by, updated_by)
- Soft deletion
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class UUIDMixin:
    """
    Mixin providing UUID primary key.

    Uses PostgreSQL's native UUID type with server-side default generation.
    """

    @declared_attr
    def id(cls) -> Mapped[UUID]:
        return mapped_column(
            PGUUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            server_default=text("gen_random_uuid()"),
            nullable=False,
        )


class TimestampMixin:
    """
    Mixin providing automatic timestamp tracking.

    Automatically sets created_at on insert and updates updated_at on every change.
    Uses timezone-aware timestamps for proper audit trails.
    """

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            server_default=func.now(),
            nullable=False,
            index=True,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            default=lambda: datetime.now(timezone.utc),
            server_default=func.now(),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        )


class AuditMixin(TimestampMixin):
    """
    Mixin for tracking who created and last modified a record.

    Extends TimestampMixin with user tracking for comprehensive audit trails.
    User IDs reference Supabase auth.users table.
    """

    @declared_attr
    def created_by(cls) -> Mapped[UUID | None]:
        return mapped_column(
            PGUUID(as_uuid=True),
            nullable=True,
            index=True,
        )

    @declared_attr
    def updated_by(cls) -> Mapped[UUID | None]:
        return mapped_column(
            PGUUID(as_uuid=True),
            nullable=True,
        )


class SoftDeleteMixin:
    """
    Mixin for soft deletion support.

    Records are marked as deleted rather than removed from the database.
    Enables recovery and maintains referential integrity.
    """

    @declared_attr
    def is_deleted(cls) -> Mapped[bool]:
        return mapped_column(
            Boolean,
            default=False,
            server_default=text("false"),
            nullable=False,
            index=True,
        )

    @declared_attr
    def deleted_at(cls) -> Mapped[datetime | None]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=True,
        )

    @declared_attr
    def deleted_by(cls) -> Mapped[UUID | None]:
        return mapped_column(
            PGUUID(as_uuid=True),
            nullable=True,
        )

    def soft_delete(self, user_id: UUID | None = None) -> None:
        """Mark this record as soft-deleted.

        Soft deletion preserves the record in the database but marks it as deleted.
        This enables recovery and maintains referential integrity with related records.

        Note: Queries must explicitly filter out soft-deleted records using
        `is_deleted=False`. Consider using a custom query filter or session event
        to automatically exclude soft-deleted records.

        Args:
            user_id: The ID of the user performing the deletion. If None, indicates
                a system-initiated deletion.

        Example:
            session.soft_delete(current_user.id)
            await db.commit()
        """
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = user_id

    def restore(self) -> None:
        """Restore a soft-deleted record.

        Reverses a soft deletion, making the record active again.
        All deletion metadata (deleted_at, deleted_by) is cleared.

        Example:
            session.restore()
            await db.commit()
        """
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class TraceableMixin:
    """
    Mixin for OpenAI Agents SDK tracing integration.

    Provides trace_id for linking database records to agent execution traces.
    Essential for debugging and audit trail correlation.
    """

    @declared_attr
    def trace_id(cls) -> Mapped[str | None]:
        return mapped_column(
            String(64),
            nullable=True,
            index=True,
            comment="OpenAI Agents SDK trace identifier",
        )
