"""Add agent metrics tables

Revision ID: 005
Revises: 004
Create Date: 2024-12-31 12:00:00.000000

Creates tables for:
- agent_metrics: Individual agent execution metrics
- aggregated_metrics: Pre-computed aggregated statistics
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent metrics tables."""

    # Create agent_metrics table
    op.create_table(
        "agent_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Execution identification
        sa.Column("trace_id", sa.String(64), nullable=True, comment="Trace ID for correlation with spans"),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Session ID for the agent execution"),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, comment="User who triggered the execution"),
        # Agent information
        sa.Column("agent_type", sa.String(50), nullable=False, comment="Type of agent executed"),
        sa.Column("agent_name", sa.String(100), nullable=True, comment="Name of the agent"),
        sa.Column("model", sa.String(50), nullable=False, comment="LLM model used"),
        # Timing metrics
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, comment="Execution start time"),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True, comment="Execution end time"),
        sa.Column("duration_ms", sa.Float, nullable=True, comment="Total execution duration in milliseconds"),
        # Token usage
        sa.Column("input_tokens", sa.Integer, nullable=True, comment="Number of input tokens"),
        sa.Column("output_tokens", sa.Integer, nullable=True, comment="Number of output tokens"),
        sa.Column("total_tokens", sa.Integer, nullable=True, comment="Total tokens (input + output)"),
        sa.Column("estimated_cost", sa.Float, nullable=True, comment="Estimated cost in USD"),
        # Execution status
        sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true"), comment="Whether execution succeeded"),
        sa.Column("error_type", sa.String(100), nullable=True, comment="Error type if execution failed"),
        sa.Column("error_message", sa.String(1000), nullable=True, comment="Error message if execution failed"),
        # Input/Output sizes
        sa.Column("input_length", sa.Integer, nullable=True, comment="Character length of input"),
        sa.Column("output_length", sa.Integer, nullable=True, comment="Character length of output"),
        # Additional context
        sa.Column("metadata", postgresql.JSONB, nullable=True, comment="Additional metadata (tool calls, handoffs, etc.)"),
        # Record timestamp
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_metrics")),
    )

    # Create indexes for agent_metrics
    op.create_index(op.f("ix_agent_metrics_trace_id"), "agent_metrics", ["trace_id"], unique=False)
    op.create_index(op.f("ix_agent_metrics_session_id"), "agent_metrics", ["session_id"], unique=False)
    op.create_index(op.f("ix_agent_metrics_user_id"), "agent_metrics", ["user_id"], unique=False)
    op.create_index(op.f("ix_agent_metrics_agent_type"), "agent_metrics", ["agent_type"], unique=False)
    op.create_index(op.f("ix_agent_metrics_model"), "agent_metrics", ["model"], unique=False)
    op.create_index(op.f("ix_agent_metrics_start_time"), "agent_metrics", ["start_time"], unique=False)
    op.create_index(op.f("ix_agent_metrics_duration_ms"), "agent_metrics", ["duration_ms"], unique=False)
    op.create_index(op.f("ix_agent_metrics_total_tokens"), "agent_metrics", ["total_tokens"], unique=False)
    op.create_index(op.f("ix_agent_metrics_success"), "agent_metrics", ["success"], unique=False)

    # Composite indexes for common queries
    op.create_index("ix_agent_metrics_agent_time", "agent_metrics", ["agent_type", "start_time"], unique=False)
    op.create_index("ix_agent_metrics_model_time", "agent_metrics", ["model", "start_time"], unique=False)
    op.create_index("ix_agent_metrics_user_time", "agent_metrics", ["user_id", "start_time"], unique=False)
    op.create_index("ix_agent_metrics_success_time", "agent_metrics", ["success", "start_time"], unique=False)

    # Create aggregated_metrics table
    op.create_table(
        "aggregated_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Time period
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False, comment="Start of aggregation period"),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False, comment="End of aggregation period"),
        sa.Column("granularity", sa.String(20), nullable=False, server_default="hourly", comment="Aggregation granularity (minute, hourly, daily, weekly)"),
        # Scope
        sa.Column("agent_type", sa.String(50), nullable=True, comment="Agent type (null for global metrics)"),
        sa.Column("model", sa.String(50), nullable=True, comment="Model (null for all models)"),
        # Execution counts
        sa.Column("total_executions", sa.Integer, nullable=False, server_default="0", comment="Total number of executions"),
        sa.Column("successful_executions", sa.Integer, nullable=False, server_default="0", comment="Number of successful executions"),
        sa.Column("failed_executions", sa.Integer, nullable=False, server_default="0", comment="Number of failed executions"),
        sa.Column("success_rate", sa.Float, nullable=True, comment="Success rate (0.0 - 1.0)"),
        # Latency statistics
        sa.Column("avg_duration_ms", sa.Float, nullable=True, comment="Average duration"),
        sa.Column("min_duration_ms", sa.Float, nullable=True, comment="Minimum duration"),
        sa.Column("max_duration_ms", sa.Float, nullable=True, comment="Maximum duration"),
        sa.Column("p50_duration_ms", sa.Float, nullable=True, comment="50th percentile (median) duration"),
        sa.Column("p95_duration_ms", sa.Float, nullable=True, comment="95th percentile duration"),
        sa.Column("p99_duration_ms", sa.Float, nullable=True, comment="99th percentile duration"),
        # Token usage statistics
        sa.Column("total_input_tokens", sa.Integer, nullable=True, comment="Total input tokens consumed"),
        sa.Column("total_output_tokens", sa.Integer, nullable=True, comment="Total output tokens generated"),
        sa.Column("total_tokens", sa.Integer, nullable=True, comment="Total tokens (input + output)"),
        sa.Column("avg_input_tokens", sa.Float, nullable=True, comment="Average input tokens per execution"),
        sa.Column("avg_output_tokens", sa.Float, nullable=True, comment="Average output tokens per execution"),
        # Cost statistics
        sa.Column("total_estimated_cost", sa.Float, nullable=True, comment="Total estimated cost"),
        # Error breakdown
        sa.Column("error_distribution", postgresql.JSONB, nullable=True, comment="Count per error type"),
        # User statistics
        sa.Column("unique_users", sa.Integer, nullable=True, comment="Number of unique users"),
        sa.Column("unique_sessions", sa.Integer, nullable=True, comment="Number of unique sessions"),
        # Raw data
        sa.Column("raw_data", postgresql.JSONB, nullable=True, comment="Additional aggregation data"),
        # Record timestamp
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_aggregated_metrics")),
    )

    # Create indexes for aggregated_metrics
    op.create_index(op.f("ix_aggregated_metrics_period_start"), "aggregated_metrics", ["period_start"], unique=False)
    op.create_index(op.f("ix_aggregated_metrics_granularity"), "aggregated_metrics", ["granularity"], unique=False)
    op.create_index(op.f("ix_aggregated_metrics_agent_type"), "aggregated_metrics", ["agent_type"], unique=False)
    op.create_index(op.f("ix_aggregated_metrics_model"), "aggregated_metrics", ["model"], unique=False)

    # Composite indexes
    op.create_index("ix_aggregated_metrics_period", "aggregated_metrics", ["period_start", "period_end"], unique=False)
    op.create_index("ix_aggregated_metrics_granularity_time", "aggregated_metrics", ["granularity", "period_start"], unique=False)
    op.create_index("ix_aggregated_metrics_agent_granularity", "aggregated_metrics", ["agent_type", "granularity", "period_start"], unique=False)


def downgrade() -> None:
    """Drop agent metrics tables."""
    op.drop_table("aggregated_metrics")
    op.drop_table("agent_metrics")
