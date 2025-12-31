"""
Trace storage models for distributed tracing.

Provides persistent storage for trace spans, enabling:
- Historical trace analysis
- Performance monitoring
- Debugging and troubleshooting
- Audit trail correlation
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import UUIDMixin


class TraceSpan(Base, UUIDMixin):
    """
    Database model for storing trace spans.

    Enables persistent storage of trace data for:
    - Historical analysis and debugging
    - Performance monitoring and alerting
    - Correlation with audit logs
    """

    __tablename__ = "trace_spans"

    # Trace identification
    trace_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Trace identifier linking related spans",
    )

    span_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        comment="Unique span identifier",
    )

    parent_span_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        comment="Parent span ID for hierarchy",
    )

    # Span metadata
    name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
        comment="Span operation name",
    )

    kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="internal",
        comment="Span kind (server, client, internal, producer, consumer)",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unset",
        index=True,
        comment="Span status (unset, ok, error)",
    )

    # Timing information
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Span start timestamp",
    )

    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Span end timestamp",
    )

    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
        comment="Span duration in milliseconds",
    )

    # Additional data
    attributes: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Span attributes/metadata",
    )

    events: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Span events/logs",
    )

    # User context (optional)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User associated with this span",
    )

    # Request context
    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="HTTP request ID for correlation",
    )

    # Service identification
    service_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        default="my-ai-actuary-backend",
        comment="Service that generated this span",
    )

    # Timestamp for record creation (different from span timing)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_trace_spans_trace_status", "trace_id", "status"),
        Index("ix_trace_spans_time_range", "start_time", "end_time"),
        Index("ix_trace_spans_user_time", "user_id", "start_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<TraceSpan(id={self.id}, trace_id={self.trace_id}, "
            f"name={self.name}, status={self.status})>"
        )

    @classmethod
    def from_span(
        cls,
        span: "Span",
        user_id: UUID | None = None,
        request_id: str | None = None,
        service_name: str = "my-ai-actuary-backend",
    ) -> "TraceSpan":
        """
        Create a TraceSpan from an in-memory Span object.

        Args:
            span: The span to persist
            user_id: Optional user ID
            request_id: Optional request ID
            service_name: Service name

        Returns:
            TraceSpan database model instance
        """
        return cls(
            trace_id=span.context.trace_id,
            span_id=span.context.span_id,
            parent_span_id=span.context.parent_span_id,
            name=span.name,
            kind=span.kind.value,
            status=span.status.value,
            start_time=span.start_time,
            end_time=span.end_time,
            duration_ms=span.duration_ms,
            attributes=span.attributes,
            events=span.events,
            user_id=user_id,
            request_id=request_id,
            service_name=service_name,
        )


# Import Span for type hints (avoid circular import at runtime)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tracing import Span
