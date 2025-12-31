"""
Orchestration models for tracking agent routing and handoffs.

Provides persistent storage for:
- Agent handoff history and audit trail
- Routing decisions and their outcomes
- Orchestration metrics for analysis
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, TraceableMixin, UUIDMixin

if TYPE_CHECKING:
    from models.session import Session


class HandoffReasonDB(str, Enum):
    """Database enum for handoff reasons."""

    INTENT_CHANGE = "intent_change"
    TASK_COMPLETION = "task_completion"
    SPECIALIZED_EXPERTISE = "specialized_expertise"
    USER_REQUEST = "user_request"
    ESCALATION = "escalation"
    APPROVAL_REQUIRED = "approval_required"


class RoutingOutcome(str, Enum):
    """Outcome of a routing decision."""

    SUCCESS = "success"
    FALLBACK = "fallback"
    ERROR = "error"
    RETRY = "retry"


class AgentHandoff(Base, UUIDMixin, AuditMixin, TraceableMixin):
    """
    Record of an agent handoff within a session.

    Tracks when and why control was transferred between agents,
    enabling analysis of conversation flow and orchestration effectiveness.
    """

    __tablename__ = "agent_handoffs"

    # Session reference
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Source and target agents
    from_agent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Agent type handing off (null for initial routing)",
    )

    to_agent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Agent type receiving handoff",
    )

    # Handoff reason and context
    reason: Mapped[HandoffReasonDB] = mapped_column(
        SQLEnum(HandoffReasonDB, name="handoff_reason", create_constraint=True),
        nullable=False,
    )

    # Context transferred during handoff
    context_transferred: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Context data transferred to new agent",
    )

    # Message that triggered the handoff
    trigger_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Truncated message that triggered the handoff",
    )

    # Confidence and intent from routing decision
    routing_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Confidence score from routing decision",
    )

    detected_intent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Intent classified during routing",
    )

    # Outcome tracking
    outcome: Mapped[RoutingOutcome | None] = mapped_column(
        SQLEnum(RoutingOutcome, name="routing_outcome", create_constraint=True),
        nullable=True,
        comment="Outcome of the handoff",
    )

    # Timing
    handoff_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        lazy="raise",
    )

    __table_args__ = (
        Index("ix_agent_handoffs_session_time", "session_id", "handoff_at"),
        Index("ix_agent_handoffs_from_to", "from_agent", "to_agent"),
    )

    def __repr__(self) -> str:
        return f"<AgentHandoff(id={self.id}, from={self.from_agent}, to={self.to_agent}, reason={self.reason.value})>"


class RoutingDecisionLog(Base, UUIDMixin, TraceableMixin):
    """
    Log of routing decisions made by the orchestrator.

    Enables analysis of routing effectiveness and intent classification accuracy.
    """

    __tablename__ = "routing_decision_logs"

    # Session reference
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message ID if applicable
    message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Routing decision details
    detected_intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    target_agent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Whether handoff was required
    handoff_required: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    # Current agent at time of decision
    current_agent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Raw decision data
    decision_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full routing decision payload",
    )

    # Outcome (updated after execution)
    outcome: Mapped[RoutingOutcome | None] = mapped_column(
        SQLEnum(RoutingOutcome, name="routing_outcome", create_constraint=True),
        nullable=True,
    )

    # User feedback (if provided)
    user_feedback: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="User feedback on routing (correct, incorrect, etc.)",
    )

    # Timing
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_routing_logs_session_time", "session_id", "decided_at"),
        Index("ix_routing_logs_intent", "detected_intent"),
    )

    def __repr__(self) -> str:
        return f"<RoutingDecisionLog(id={self.id}, intent={self.detected_intent}, agent={self.target_agent})>"


class OrchestrationMetrics(Base, UUIDMixin):
    """
    Aggregated metrics for orchestration performance.

    Stores periodic snapshots of orchestration statistics
    for monitoring and optimization.
    """

    __tablename__ = "orchestration_metrics"

    # Time period for the metrics
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Aggregation level (hourly, daily, weekly)
    aggregation: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="hourly",
    )

    # Counts
    total_messages: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    total_handoffs: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    total_sessions: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    # Per-agent stats
    agent_message_counts: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Message count per agent type",
    )

    agent_handoff_counts: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Handoff count per agent type",
    )

    # Intent distribution
    intent_distribution: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Count per detected intent",
    )

    # Performance metrics
    avg_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average routing confidence",
    )

    success_rate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Percentage of successful routings",
    )

    # Raw data for debugging
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_orchestration_metrics_period", "period_start", "period_end"),
        Index("ix_orchestration_metrics_aggregation", "aggregation"),
    )

    def __repr__(self) -> str:
        return f"<OrchestrationMetrics(period={self.period_start} - {self.period_end}, messages={self.total_messages})>"
