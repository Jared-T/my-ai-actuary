"""
Metrics API routes for agent performance monitoring.

Provides endpoints for:
- Querying agent execution metrics
- Viewing performance summaries and statistics
- Time series data for charting
- Breakdowns by agent type and model
"""

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.metrics_service import MetricsService, get_metrics_service

router = APIRouter(prefix="/metrics", tags=["Metrics"])


# Request/Response Models
class MetricInfo(BaseModel):
    """Information about a single agent metric."""

    id: str = Field(description="Metric ID")
    trace_id: Optional[str] = Field(default=None, description="Trace ID")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    user_id: Optional[str] = Field(default=None, description="User ID")
    agent_type: str = Field(description="Agent type")
    agent_name: Optional[str] = Field(default=None, description="Agent name")
    model: str = Field(description="LLM model used")
    start_time: str = Field(description="Execution start time")
    end_time: Optional[str] = Field(default=None, description="Execution end time")
    duration_ms: Optional[float] = Field(default=None, description="Duration in ms")
    input_tokens: Optional[int] = Field(default=None, description="Input tokens")
    output_tokens: Optional[int] = Field(default=None, description="Output tokens")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated cost USD")
    success: bool = Field(description="Whether execution succeeded")
    error_type: Optional[str] = Field(default=None, description="Error type if failed")
    input_length: Optional[int] = Field(default=None, description="Input character length")
    output_length: Optional[int] = Field(default=None, description="Output character length")
    created_at: str = Field(description="Record creation time")


class MetricListResponse(BaseModel):
    """Response model for listing metrics."""

    metrics: list[MetricInfo] = Field(description="List of metrics")
    total: int = Field(description="Total number of metrics returned")


class ExecutionStats(BaseModel):
    """Execution count statistics."""

    total: int = Field(description="Total executions")
    successful: int = Field(description="Successful executions")
    failed: int = Field(description="Failed executions")
    success_rate: float = Field(description="Success rate (0.0-1.0)")


class LatencyStats(BaseModel):
    """Latency statistics."""

    avg_ms: float = Field(description="Average duration in ms")


class TokenStats(BaseModel):
    """Token usage statistics."""

    total_input: int = Field(description="Total input tokens")
    total_output: int = Field(description="Total output tokens")
    total: int = Field(description="Total tokens")


class CostStats(BaseModel):
    """Cost statistics."""

    total_estimated_usd: float = Field(description="Total estimated cost in USD")


class UserStats(BaseModel):
    """User statistics."""

    unique_users: int = Field(description="Number of unique users")
    unique_sessions: int = Field(description="Number of unique sessions")


class PeriodInfo(BaseModel):
    """Time period information."""

    from_: str = Field(alias="from", description="Period start")
    to: str = Field(description="Period end")


class FilterInfo(BaseModel):
    """Applied filters."""

    agent_type: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)


class MetricsSummary(BaseModel):
    """Summary statistics for metrics."""

    period: PeriodInfo = Field(description="Time period")
    filters: FilterInfo = Field(description="Applied filters")
    executions: ExecutionStats = Field(description="Execution statistics")
    latency: LatencyStats = Field(description="Latency statistics")
    tokens: TokenStats = Field(description="Token usage statistics")
    cost: CostStats = Field(description="Cost statistics")
    users: UserStats = Field(description="User statistics")


class LatencyPercentiles(BaseModel):
    """Latency percentile statistics."""

    min: float = Field(description="Minimum duration")
    max: float = Field(description="Maximum duration")
    avg: float = Field(description="Average duration")
    p50: float = Field(description="50th percentile (median)")
    p75: float = Field(description="75th percentile")
    p90: float = Field(description="90th percentile")
    p95: float = Field(description="95th percentile")
    p99: float = Field(description="99th percentile")


class AgentBreakdownItem(BaseModel):
    """Breakdown statistics for a single agent type."""

    agent_type: str = Field(description="Agent type")
    total_executions: int = Field(description="Total executions")
    successful_executions: int = Field(description="Successful executions")
    failed_executions: int = Field(description="Failed executions")
    success_rate: float = Field(description="Success rate")
    avg_duration_ms: float = Field(description="Average duration in ms")
    total_tokens: int = Field(description="Total tokens used")
    total_cost_usd: float = Field(description="Total cost in USD")


class ModelBreakdownItem(BaseModel):
    """Breakdown statistics for a single model."""

    model: str = Field(description="Model name")
    total_executions: int = Field(description="Total executions")
    successful_executions: int = Field(description="Successful executions")
    success_rate: float = Field(description="Success rate")
    avg_duration_ms: float = Field(description="Average duration in ms")
    total_input_tokens: int = Field(description="Total input tokens")
    total_output_tokens: int = Field(description="Total output tokens")
    total_tokens: int = Field(description="Total tokens")
    total_cost_usd: float = Field(description="Total cost in USD")


class TimeSeriesPoint(BaseModel):
    """A single point in a time series."""

    timestamp: Optional[str] = Field(description="Time bucket")
    total_executions: int = Field(description="Total executions")
    successful_executions: int = Field(description="Successful executions")
    failed_executions: int = Field(description="Failed executions")
    success_rate: float = Field(description="Success rate")
    avg_duration_ms: float = Field(description="Average duration in ms")
    total_tokens: int = Field(description="Total tokens")


class ErrorBreakdownItem(BaseModel):
    """Error type breakdown."""

    error_type: str = Field(description="Error type")
    count: int = Field(description="Number of occurrences")


# Endpoints
@router.get(
    "",
    response_model=MetricListResponse,
    summary="List agent metrics",
    description="Get a list of agent execution metrics with optional filtering.",
)
async def list_metrics(
    agent_type: Optional[str] = Query(default=None, description="Filter by agent type"),
    model: Optional[str] = Query(default=None, description="Filter by model"),
    user_id: Optional[UUID] = Query(default=None, description="Filter by user"),
    session_id: Optional[UUID] = Query(default=None, description="Filter by session"),
    success: Optional[bool] = Query(default=None, description="Filter by success status"),
    from_time: Optional[datetime] = Query(default=None, description="Filter from time"),
    to_time: Optional[datetime] = Query(default=None, description="Filter to time"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Result offset"),
    db: AsyncSession = Depends(get_db),
) -> MetricListResponse:
    """List agent execution metrics."""
    service = MetricsService(db)

    metrics = await service.get_metrics(
        agent_type=agent_type,
        model=model,
        user_id=user_id,
        session_id=session_id,
        success=success,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )

    return MetricListResponse(
        metrics=[
            MetricInfo(
                id=str(m.id),
                trace_id=m.trace_id,
                session_id=str(m.session_id) if m.session_id else None,
                user_id=str(m.user_id) if m.user_id else None,
                agent_type=m.agent_type,
                agent_name=m.agent_name,
                model=m.model,
                start_time=m.start_time.isoformat(),
                end_time=m.end_time.isoformat() if m.end_time else None,
                duration_ms=m.duration_ms,
                input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                total_tokens=m.total_tokens,
                estimated_cost=m.estimated_cost,
                success=m.success,
                error_type=m.error_type,
                input_length=m.input_length,
                output_length=m.output_length,
                created_at=m.created_at.isoformat(),
            )
            for m in metrics
        ],
        total=len(metrics),
    )


@router.get(
    "/summary",
    response_model=MetricsSummary,
    summary="Get metrics summary",
    description="Get summary statistics for agent metrics.",
)
async def get_summary(
    agent_type: Optional[str] = Query(default=None, description="Filter by agent type"),
    model: Optional[str] = Query(default=None, description="Filter by model"),
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> MetricsSummary:
    """Get summary statistics."""
    service = MetricsService(db)

    summary = await service.get_summary(
        agent_type=agent_type,
        model=model,
        from_time=from_time,
        to_time=to_time,
    )

    return MetricsSummary(
        period=PeriodInfo(**{"from": summary["period"]["from"], "to": summary["period"]["to"]}),
        filters=FilterInfo(**summary["filters"]),
        executions=ExecutionStats(**summary["executions"]),
        latency=LatencyStats(**summary["latency"]),
        tokens=TokenStats(**summary["tokens"]),
        cost=CostStats(**summary["cost"]),
        users=UserStats(**summary["users"]),
    )


@router.get(
    "/latency",
    response_model=LatencyPercentiles,
    summary="Get latency percentiles",
    description="Get latency percentile statistics.",
)
async def get_latency_percentiles(
    agent_type: Optional[str] = Query(default=None, description="Filter by agent type"),
    model: Optional[str] = Query(default=None, description="Filter by model"),
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> LatencyPercentiles:
    """Get latency percentiles."""
    service = MetricsService(db)

    percentiles = await service.get_latency_percentiles(
        agent_type=agent_type,
        model=model,
        from_time=from_time,
        to_time=to_time,
    )

    return LatencyPercentiles(**percentiles)


@router.get(
    "/agents",
    response_model=list[AgentBreakdownItem],
    summary="Get agent breakdown",
    description="Get metrics breakdown by agent type.",
)
async def get_agent_breakdown(
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> list[AgentBreakdownItem]:
    """Get breakdown by agent type."""
    service = MetricsService(db)

    breakdown = await service.get_agent_breakdown(
        from_time=from_time,
        to_time=to_time,
    )

    return [AgentBreakdownItem(**item) for item in breakdown]


@router.get(
    "/models",
    response_model=list[ModelBreakdownItem],
    summary="Get model breakdown",
    description="Get metrics breakdown by model.",
)
async def get_model_breakdown(
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> list[ModelBreakdownItem]:
    """Get breakdown by model."""
    service = MetricsService(db)

    breakdown = await service.get_model_breakdown(
        from_time=from_time,
        to_time=to_time,
    )

    return [ModelBreakdownItem(**item) for item in breakdown]


@router.get(
    "/timeseries",
    response_model=list[TimeSeriesPoint],
    summary="Get time series data",
    description="Get time-bucketed metrics for charting.",
)
async def get_time_series(
    granularity: Literal["minute", "hour", "day"] = Query(
        default="hour", description="Time bucket size"
    ),
    agent_type: Optional[str] = Query(default=None, description="Filter by agent type"),
    model: Optional[str] = Query(default=None, description="Filter by model"),
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> list[TimeSeriesPoint]:
    """Get time series data."""
    service = MetricsService(db)

    series = await service.get_time_series(
        granularity=granularity,
        agent_type=agent_type,
        model=model,
        from_time=from_time,
        to_time=to_time,
    )

    return [TimeSeriesPoint(**point) for point in series]


@router.get(
    "/errors",
    response_model=list[ErrorBreakdownItem],
    summary="Get error breakdown",
    description="Get breakdown of errors by type.",
)
async def get_error_breakdown(
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> list[ErrorBreakdownItem]:
    """Get error breakdown."""
    service = MetricsService(db)

    errors = await service.get_error_breakdown(
        from_time=from_time,
        to_time=to_time,
    )

    return [ErrorBreakdownItem(**item) for item in errors]


@router.post(
    "/aggregate",
    summary="Trigger metrics aggregation",
    description="Create aggregated metrics records for a time period.",
)
async def aggregate_metrics(
    granularity: Literal["minute", "hourly", "daily", "weekly"] = Query(
        default="hourly", description="Aggregation granularity"
    ),
    from_time: Optional[datetime] = Query(default=None, description="Start of period"),
    to_time: Optional[datetime] = Query(default=None, description="End of period"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger metrics aggregation."""
    service = MetricsService(db)

    count = await service.aggregate_metrics(
        granularity=granularity,
        from_time=from_time,
        to_time=to_time,
    )

    return {
        "status": "success",
        "message": f"Created {count} aggregation records",
        "count": count,
    }


@router.get(
    "/dashboard",
    summary="Get dashboard data",
    description="Get all data needed for the metrics dashboard in one call.",
)
async def get_dashboard_data(
    from_time: Optional[datetime] = Query(default=None, description="Start of time range"),
    to_time: Optional[datetime] = Query(default=None, description="End of time range"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get all dashboard data in one call."""
    service = MetricsService(db)

    # Fetch all data in parallel (conceptually - SQLAlchemy handles sequentially)
    summary = await service.get_summary(from_time=from_time, to_time=to_time)
    latency = await service.get_latency_percentiles(from_time=from_time, to_time=to_time)
    agents = await service.get_agent_breakdown(from_time=from_time, to_time=to_time)
    models = await service.get_model_breakdown(from_time=from_time, to_time=to_time)
    timeseries = await service.get_time_series(
        granularity="hour", from_time=from_time, to_time=to_time
    )
    errors = await service.get_error_breakdown(from_time=from_time, to_time=to_time)

    return {
        "summary": summary,
        "latency_percentiles": latency,
        "by_agent": agents,
        "by_model": models,
        "timeseries": timeseries,
        "errors": errors,
    }
