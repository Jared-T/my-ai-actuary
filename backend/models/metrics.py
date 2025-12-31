"""
Agent performance metrics models.

Provides persistent storage for:
- Agent execution metrics (latency, success rates, token usage)
- Aggregated performance statistics
- Performance trends over time
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import UUIDMixin


class MetricType(str, Enum):
    """Types of metrics collected."""

    AGENT_EXECUTION = "agent_execution"
    TOKEN_USAGE = "token_usage"
    LATENCY = "latency"
    ERROR = "error"
    SYSTEM = "system"


class AgentMetric(Base, UUIDMixin):
    """
    Individual agent execution metric record.

    Captures detailed metrics for each agent invocation including:
    - Execution timing and latency
    - Token consumption (input, output, total)
    - Success/failure status
    - Model and configuration used
    """

    __tablename__ = "agent_metrics"

    # Execution identification
    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Trace ID for correlation with spans",
    )

    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Session ID for the agent execution",
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who triggered the execution",
    )

    # Agent information
    agent_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of agent executed",
    )

    agent_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Name of the agent",
    )

    model: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="LLM model used",
    )

    # Timing metrics
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Execution start time",
    )

    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Execution end time",
    )

    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
        comment="Total execution duration in milliseconds",
    )

    # Token usage
    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of input tokens",
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of output tokens",
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Total tokens (input + output)",
    )

    # Cost tracking (optional)
    estimated_cost: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Estimated cost in USD",
    )

    # Execution status
    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Whether execution succeeded",
    )

    error_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Error type if execution failed",
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Error message if execution failed",
    )

    # Input/Output sizes
    input_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character length of input",
    )

    output_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character length of output",
    )

    # Additional context
    # Named metric_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    metric_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional metadata (tool calls, handoffs, etc.)",
    )

    # Record timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_agent_metrics_agent_time", "agent_type", "start_time"),
        Index("ix_agent_metrics_model_time", "model", "start_time"),
        Index("ix_agent_metrics_user_time", "user_id", "start_time"),
        Index("ix_agent_metrics_success_time", "success", "start_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentMetric(id={self.id}, agent={self.agent_type}, "
            f"duration={self.duration_ms}ms, success={self.success})>"
        )


class AggregatedMetrics(Base, UUIDMixin):
    """
    Aggregated metrics for performance monitoring dashboards.

    Stores pre-computed aggregations over time periods for:
    - Per-agent performance statistics
    - Token usage summaries
    - Success/failure rates
    - Latency percentiles
    """

    __tablename__ = "aggregated_metrics"

    # Time period
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Start of aggregation period",
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="End of aggregation period",
    )

    # Aggregation granularity
    granularity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="hourly",
        index=True,
        comment="Aggregation granularity (minute, hourly, daily, weekly)",
    )

    # Scope (can be per-agent or global)
    agent_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Agent type (null for global metrics)",
    )

    model: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Model (null for all models)",
    )

    # Execution counts
    total_executions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of executions",
    )

    successful_executions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of successful executions",
    )

    failed_executions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of failed executions",
    )

    # Success rate
    success_rate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Success rate (0.0 - 1.0)",
    )

    # Latency statistics (in milliseconds)
    avg_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average duration",
    )

    min_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Minimum duration",
    )

    max_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Maximum duration",
    )

    p50_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="50th percentile (median) duration",
    )

    p95_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="95th percentile duration",
    )

    p99_duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="99th percentile duration",
    )

    # Token usage statistics
    total_input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total input tokens consumed",
    )

    total_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total output tokens generated",
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total tokens (input + output)",
    )

    avg_input_tokens: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average input tokens per execution",
    )

    avg_output_tokens: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average output tokens per execution",
    )

    # Cost statistics
    total_estimated_cost: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Total estimated cost",
    )

    # Error breakdown
    error_distribution: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Count per error type",
    )

    # Additional statistics
    unique_users: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of unique users",
    )

    unique_sessions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of unique sessions",
    )

    # Raw data for custom analysis
    raw_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional aggregation data",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_aggregated_metrics_period", "period_start", "period_end"),
        Index("ix_aggregated_metrics_granularity_time", "granularity", "period_start"),
        Index("ix_aggregated_metrics_agent_granularity", "agent_type", "granularity", "period_start"),
    )

    def __repr__(self) -> str:
        agent = self.agent_type or "global"
        return (
            f"<AggregatedMetrics(period={self.period_start}, "
            f"agent={agent}, executions={self.total_executions})>"
        )
