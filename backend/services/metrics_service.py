"""
Metrics collection service for agent performance monitoring.

Provides:
- Real-time metrics collection during agent execution
- Aggregation of metrics over time periods
- Query interfaces for dashboards and reporting
- Token usage and cost estimation
"""

import os
import statistics
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.metrics import AgentMetric, AggregatedMetrics

logger = get_logger(__name__)

# Token pricing - can be overridden via environment variables
# Format: MODEL_PRICING_<MODEL_NAME>_INPUT and MODEL_PRICING_<MODEL_NAME>_OUTPUT
# Values are price per 1000 tokens in USD
DEFAULT_TOKEN_PRICING = {
    "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
    "gpt-4-turbo": {"input": 0.01 / 1000, "output": 0.03 / 1000},
    "gpt-4-turbo-preview": {"input": 0.01 / 1000, "output": 0.03 / 1000},
    "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
    "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
    "gpt-3.5-turbo": {"input": 0.0005 / 1000, "output": 0.0015 / 1000},
    # Default for unknown models
    "default": {"input": 0.01 / 1000, "output": 0.03 / 1000},
}


def get_token_pricing(model: str) -> dict[str, float]:
    """
    Get token pricing for a model, checking environment overrides first.

    Args:
        model: The model name

    Returns:
        Dict with 'input' and 'output' pricing per token
    """
    # Check for environment variable overrides
    model_key = model.upper().replace("-", "_").replace(".", "_")
    input_price_env = f"MODEL_PRICING_{model_key}_INPUT"
    output_price_env = f"MODEL_PRICING_{model_key}_OUTPUT"

    input_price = os.environ.get(input_price_env)
    output_price = os.environ.get(output_price_env)

    if input_price and output_price:
        try:
            return {
                "input": float(input_price) / 1000,
                "output": float(output_price) / 1000,
            }
        except ValueError:
            logger.warning(
                "Invalid pricing environment variables",
                model=model,
                input_env=input_price_env,
                output_env=output_price_env,
            )

    # Fall back to default pricing
    return DEFAULT_TOKEN_PRICING.get(model, DEFAULT_TOKEN_PRICING["default"])


class MetricsCollector:
    """
    Collects and stores agent execution metrics.

    Thread-safe singleton collector that can be used to record metrics
    during agent execution.
    """

    _instance: Optional["MetricsCollector"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        pass

    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Get the singleton metrics collector instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate the cost of an execution based on token usage.

        Args:
            model: The model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pricing = get_token_pricing(model)
        return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])

    async def record_metric(
        self,
        db: AsyncSession,
        agent_type: str,
        model: str,
        start_time: datetime,
        end_time: datetime | None = None,
        duration_ms: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        success: bool = True,
        error_type: str | None = None,
        error_message: str | None = None,
        input_length: int | None = None,
        output_length: int | None = None,
        trace_id: str | None = None,
        session_id: UUID | None = None,
        user_id: UUID | None = None,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMetric:
        """
        Record a single agent execution metric.

        Args:
            db: Database session
            agent_type: Type of agent
            model: LLM model used
            start_time: Execution start time
            end_time: Execution end time
            duration_ms: Duration in milliseconds
            input_tokens: Input token count
            output_tokens: Output token count
            success: Whether execution succeeded
            error_type: Error type if failed
            error_message: Error message if failed
            input_length: Input character length
            output_length: Output character length
            trace_id: Trace ID for correlation
            session_id: Session ID
            user_id: User ID
            agent_name: Agent name
            metadata: Additional metadata

        Returns:
            Created AgentMetric record
        """
        # Calculate duration if not provided
        if duration_ms is None and end_time is not None:
            delta = end_time - start_time
            duration_ms = delta.total_seconds() * 1000

        # Calculate total tokens
        total_tokens = None
        if input_tokens is not None or output_tokens is not None:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        # Estimate cost
        estimated_cost = None
        if input_tokens is not None and output_tokens is not None:
            estimated_cost = self.estimate_cost(model, input_tokens, output_tokens)

        metric = AgentMetric(
            agent_type=agent_type,
            agent_name=agent_name,
            model=model,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            success=success,
            error_type=error_type,
            error_message=error_message,
            input_length=input_length,
            output_length=output_length,
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            metric_metadata=metadata or {},
        )

        db.add(metric)
        await db.flush()

        logger.debug(
            "Recorded agent metric",
            agent_type=agent_type,
            model=model,
            duration_ms=duration_ms,
            success=success,
            trace_id=trace_id,
        )

        return metric


class MetricsService:
    """
    Service for querying and aggregating agent metrics.

    Provides methods for:
    - Querying individual metrics
    - Computing aggregations
    - Generating performance reports
    """

    # Default time range in hours for different granularities
    DEFAULT_TIME_RANGES = {
        "minute": 1,
        "hour": 24,
        "day": 720,  # 30 days
        "hourly": 24,
        "daily": 168,  # 7 days
        "weekly": 672,  # 4 weeks
    }

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the metrics service.

        Args:
            db: Database session
        """
        self.db = db

    def _default_time_range(
        self,
        from_time: datetime | None,
        to_time: datetime | None,
        granularity: str = "hour",
    ) -> tuple[datetime, datetime]:
        """
        Apply default time range if not specified.

        Args:
            from_time: Start of time range (optional)
            to_time: End of time range (optional)
            granularity: Granularity to determine default range

        Returns:
            Tuple of (from_time, to_time) with defaults applied
        """
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            hours = self.DEFAULT_TIME_RANGES.get(granularity, 24)
            from_time = to_time - timedelta(hours=hours)
        return from_time, to_time

    async def get_metrics(
        self,
        agent_type: str | None = None,
        model: str | None = None,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        success: bool | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentMetric]:
        """
        Query agent metrics with filters.

        Args:
            agent_type: Filter by agent type
            model: Filter by model
            user_id: Filter by user
            session_id: Filter by session
            success: Filter by success status
            from_time: Filter by start time (from)
            to_time: Filter by start time (to)
            limit: Maximum results
            offset: Result offset

        Returns:
            List of matching metrics
        """
        stmt = select(AgentMetric)

        # Apply filters
        filters = []
        if agent_type:
            filters.append(AgentMetric.agent_type == agent_type)
        if model:
            filters.append(AgentMetric.model == model)
        if user_id:
            filters.append(AgentMetric.user_id == user_id)
        if session_id:
            filters.append(AgentMetric.session_id == session_id)
        if success is not None:
            filters.append(AgentMetric.success == success)
        if from_time:
            filters.append(AgentMetric.start_time >= from_time)
        if to_time:
            filters.append(AgentMetric.start_time <= to_time)

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(AgentMetric.start_time.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_summary(
        self,
        agent_type: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get summary statistics for metrics.

        Args:
            agent_type: Filter by agent type
            model: Filter by model
            from_time: Start of time range
            to_time: End of time range

        Returns:
            Dictionary with summary statistics
        """
        from_time, to_time = self._default_time_range(from_time, to_time)

        # Build base query
        filters = [
            AgentMetric.start_time >= from_time,
            AgentMetric.start_time <= to_time,
        ]
        if agent_type:
            filters.append(AgentMetric.agent_type == agent_type)
        if model:
            filters.append(AgentMetric.model == model)

        # Total executions
        count_stmt = select(func.count(AgentMetric.id)).where(and_(*filters))
        total_result = await self.db.execute(count_stmt)
        total_executions = total_result.scalar() or 0

        # Successful executions
        success_stmt = select(func.count(AgentMetric.id)).where(
            and_(*filters, AgentMetric.success == True)
        )
        success_result = await self.db.execute(success_stmt)
        successful_executions = success_result.scalar() or 0

        # Failed executions
        failed_executions = total_executions - successful_executions

        # Success rate
        success_rate = (
            successful_executions / total_executions if total_executions > 0 else 0.0
        )

        # Average duration
        avg_stmt = select(func.avg(AgentMetric.duration_ms)).where(and_(*filters))
        avg_result = await self.db.execute(avg_stmt)
        avg_duration = avg_result.scalar() or 0.0

        # Token sums
        tokens_stmt = select(
            func.sum(AgentMetric.input_tokens),
            func.sum(AgentMetric.output_tokens),
            func.sum(AgentMetric.total_tokens),
            func.sum(AgentMetric.estimated_cost),
        ).where(and_(*filters))
        tokens_result = await self.db.execute(tokens_stmt)
        tokens_row = tokens_result.one()

        # Unique users and sessions
        users_stmt = select(func.count(func.distinct(AgentMetric.user_id))).where(
            and_(*filters, AgentMetric.user_id.isnot(None))
        )
        users_result = await self.db.execute(users_stmt)
        unique_users = users_result.scalar() or 0

        sessions_stmt = select(func.count(func.distinct(AgentMetric.session_id))).where(
            and_(*filters, AgentMetric.session_id.isnot(None))
        )
        sessions_result = await self.db.execute(sessions_stmt)
        unique_sessions = sessions_result.scalar() or 0

        return {
            "period": {
                "from": from_time.isoformat(),
                "to": to_time.isoformat(),
            },
            "filters": {
                "agent_type": agent_type,
                "model": model,
            },
            "executions": {
                "total": total_executions,
                "successful": successful_executions,
                "failed": failed_executions,
                "success_rate": round(success_rate, 4),
            },
            "latency": {
                "avg_ms": round(avg_duration, 2) if avg_duration else 0.0,
            },
            "tokens": {
                "total_input": tokens_row[0] or 0,
                "total_output": tokens_row[1] or 0,
                "total": tokens_row[2] or 0,
            },
            "cost": {
                "total_estimated_usd": round(tokens_row[3] or 0, 4),
            },
            "users": {
                "unique_users": unique_users,
                "unique_sessions": unique_sessions,
            },
        }

    async def get_latency_percentiles(
        self,
        agent_type: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        max_sample_size: int = 10000,
    ) -> dict[str, float]:
        """
        Calculate latency percentiles.

        Uses database-level aggregation when possible, with a fallback to
        sampling for very large datasets to prevent memory issues.

        Args:
            agent_type: Filter by agent type
            model: Filter by model
            from_time: Start of time range
            to_time: End of time range
            max_sample_size: Maximum number of records to load for percentile calculation

        Returns:
            Dictionary with percentile values
        """
        from_time, to_time = self._default_time_range(from_time, to_time)

        # Build filters
        filters = [
            AgentMetric.start_time >= from_time,
            AgentMetric.start_time <= to_time,
            AgentMetric.duration_ms.isnot(None),
        ]
        if agent_type:
            filters.append(AgentMetric.agent_type == agent_type)
        if model:
            filters.append(AgentMetric.model == model)

        # First, get count to check if we need sampling
        count_stmt = select(func.count(AgentMetric.id)).where(and_(*filters))
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar() or 0

        if total_count == 0:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        # Get basic stats from database (always efficient)
        stats_stmt = select(
            func.min(AgentMetric.duration_ms),
            func.max(AgentMetric.duration_ms),
            func.avg(AgentMetric.duration_ms),
        ).where(and_(*filters))
        stats_result = await self.db.execute(stats_stmt)
        stats_row = stats_result.one()

        # For percentiles, sample if dataset is too large
        if total_count > max_sample_size:
            # Use random sampling via TABLESAMPLE or ORDER BY RANDOM()
            # For simplicity, we use LIMIT with ORDER BY for approximate percentiles
            logger.info(
                "Sampling for percentile calculation",
                total_count=total_count,
                sample_size=max_sample_size,
            )
            stmt = (
                select(AgentMetric.duration_ms)
                .where(and_(*filters))
                .order_by(func.random())
                .limit(max_sample_size)
            )
        else:
            stmt = select(AgentMetric.duration_ms).where(and_(*filters))

        result = await self.db.execute(stmt)
        durations = [row[0] for row in result.all() if row[0] is not None]

        if not durations:
            return {
                "min": round(stats_row[0] or 0.0, 2),
                "max": round(stats_row[1] or 0.0, 2),
                "avg": round(stats_row[2] or 0.0, 2),
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        durations.sort()
        n = len(durations)

        def percentile(p: float) -> float:
            idx = int((p / 100) * n)
            idx = min(idx, n - 1)
            return round(durations[idx], 2)

        return {
            "min": round(min(durations), 2),
            "max": round(max(durations), 2),
            "avg": round(statistics.mean(durations), 2),
            "p50": percentile(50),
            "p75": percentile(75),
            "p90": percentile(90),
            "p95": percentile(95),
            "p99": percentile(99),
        }

    async def get_agent_breakdown(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get metrics breakdown by agent type.

        Args:
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of per-agent statistics
        """
        # Default time range
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            from_time = to_time - timedelta(hours=24)

        stmt = (
            select(
                AgentMetric.agent_type,
                func.count(AgentMetric.id).label("total"),
                func.sum(func.cast(AgentMetric.success, Integer)).label("successful"),
                func.avg(AgentMetric.duration_ms).label("avg_duration"),
                func.sum(AgentMetric.total_tokens).label("total_tokens"),
                func.sum(AgentMetric.estimated_cost).label("total_cost"),
            )
            .where(
                and_(
                    AgentMetric.start_time >= from_time,
                    AgentMetric.start_time <= to_time,
                )
            )
            .group_by(AgentMetric.agent_type)
            .order_by(func.count(AgentMetric.id).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "agent_type": row[0],
                "total_executions": row[1],
                "successful_executions": row[2] or 0,
                "failed_executions": row[1] - (row[2] or 0),
                "success_rate": round((row[2] or 0) / row[1], 4) if row[1] > 0 else 0.0,
                "avg_duration_ms": round(row[3] or 0, 2),
                "total_tokens": row[4] or 0,
                "total_cost_usd": round(row[5] or 0, 4),
            }
            for row in rows
        ]

    async def get_model_breakdown(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get metrics breakdown by model.

        Args:
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of per-model statistics
        """
        # Default time range
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            from_time = to_time - timedelta(hours=24)

        stmt = (
            select(
                AgentMetric.model,
                func.count(AgentMetric.id).label("total"),
                func.sum(func.cast(AgentMetric.success, Integer)).label("successful"),
                func.avg(AgentMetric.duration_ms).label("avg_duration"),
                func.sum(AgentMetric.input_tokens).label("input_tokens"),
                func.sum(AgentMetric.output_tokens).label("output_tokens"),
                func.sum(AgentMetric.total_tokens).label("total_tokens"),
                func.sum(AgentMetric.estimated_cost).label("total_cost"),
            )
            .where(
                and_(
                    AgentMetric.start_time >= from_time,
                    AgentMetric.start_time <= to_time,
                )
            )
            .group_by(AgentMetric.model)
            .order_by(func.count(AgentMetric.id).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "model": row[0],
                "total_executions": row[1],
                "successful_executions": row[2] or 0,
                "success_rate": round((row[2] or 0) / row[1], 4) if row[1] > 0 else 0.0,
                "avg_duration_ms": round(row[3] or 0, 2),
                "total_input_tokens": row[4] or 0,
                "total_output_tokens": row[5] or 0,
                "total_tokens": row[6] or 0,
                "total_cost_usd": round(row[7] or 0, 4),
            }
            for row in rows
        ]

    async def get_time_series(
        self,
        granularity: Literal["minute", "hour", "day"] = "hour",
        agent_type: str | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get time series data for charting.

        Args:
            granularity: Time bucket size
            agent_type: Filter by agent type
            model: Filter by model
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of time-bucketed statistics
        """
        # Default time range based on granularity
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            if granularity == "minute":
                from_time = to_time - timedelta(hours=1)
            elif granularity == "hour":
                from_time = to_time - timedelta(hours=24)
            else:  # day
                from_time = to_time - timedelta(days=30)

        # Build filters
        filters = [
            AgentMetric.start_time >= from_time,
            AgentMetric.start_time <= to_time,
        ]
        if agent_type:
            filters.append(AgentMetric.agent_type == agent_type)
        if model:
            filters.append(AgentMetric.model == model)

        # Use date_trunc for time bucketing
        time_bucket = func.date_trunc(granularity, AgentMetric.start_time)

        stmt = (
            select(
                time_bucket.label("bucket"),
                func.count(AgentMetric.id).label("total"),
                func.sum(func.cast(AgentMetric.success, Integer)).label("successful"),
                func.avg(AgentMetric.duration_ms).label("avg_duration"),
                func.sum(AgentMetric.total_tokens).label("total_tokens"),
            )
            .where(and_(*filters))
            .group_by(time_bucket)
            .order_by(time_bucket)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "timestamp": row[0].isoformat() if row[0] else None,
                "total_executions": row[1],
                "successful_executions": row[2] or 0,
                "failed_executions": row[1] - (row[2] or 0),
                "success_rate": round((row[2] or 0) / row[1], 4) if row[1] > 0 else 0.0,
                "avg_duration_ms": round(row[3] or 0, 2),
                "total_tokens": row[4] or 0,
            }
            for row in rows
        ]

    async def get_error_breakdown(
        self,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get breakdown of errors by type.

        Args:
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of error type statistics
        """
        # Default time range
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            from_time = to_time - timedelta(hours=24)

        stmt = (
            select(
                AgentMetric.error_type,
                func.count(AgentMetric.id).label("count"),
            )
            .where(
                and_(
                    AgentMetric.start_time >= from_time,
                    AgentMetric.start_time <= to_time,
                    AgentMetric.success == False,
                    AgentMetric.error_type.isnot(None),
                )
            )
            .group_by(AgentMetric.error_type)
            .order_by(func.count(AgentMetric.id).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "error_type": row[0],
                "count": row[1],
            }
            for row in rows
        ]

    async def aggregate_metrics(
        self,
        granularity: Literal["minute", "hourly", "daily", "weekly"] = "hourly",
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> int:
        """
        Create aggregated metrics records for a time period.

        Args:
            granularity: Aggregation granularity
            from_time: Start of aggregation period
            to_time: End of aggregation period

        Returns:
            Number of aggregation records created
        """
        # Default time range
        if to_time is None:
            to_time = datetime.now(timezone.utc)
        if from_time is None:
            if granularity == "minute":
                from_time = to_time - timedelta(hours=1)
            elif granularity == "hourly":
                from_time = to_time - timedelta(hours=24)
            elif granularity == "daily":
                from_time = to_time - timedelta(days=7)
            else:  # weekly
                from_time = to_time - timedelta(weeks=4)

        # Get summary for the period
        summary = await self.get_summary(from_time=from_time, to_time=to_time)
        latency = await self.get_latency_percentiles(from_time=from_time, to_time=to_time)
        errors = await self.get_error_breakdown(from_time=from_time, to_time=to_time)

        # Create global aggregation record
        global_agg = AggregatedMetrics(
            period_start=from_time,
            period_end=to_time,
            granularity=granularity,
            agent_type=None,  # Global
            model=None,  # All models
            total_executions=summary["executions"]["total"],
            successful_executions=summary["executions"]["successful"],
            failed_executions=summary["executions"]["failed"],
            success_rate=summary["executions"]["success_rate"],
            avg_duration_ms=summary["latency"]["avg_ms"],
            min_duration_ms=latency["min"],
            max_duration_ms=latency["max"],
            p50_duration_ms=latency["p50"],
            p95_duration_ms=latency["p95"],
            p99_duration_ms=latency["p99"],
            total_input_tokens=summary["tokens"]["total_input"],
            total_output_tokens=summary["tokens"]["total_output"],
            total_tokens=summary["tokens"]["total"],
            total_estimated_cost=summary["cost"]["total_estimated_usd"],
            error_distribution={e["error_type"]: e["count"] for e in errors},
            unique_users=summary["users"]["unique_users"],
            unique_sessions=summary["users"]["unique_sessions"],
        )

        self.db.add(global_agg)

        # Create per-agent aggregations
        agents = await self.get_agent_breakdown(from_time=from_time, to_time=to_time)
        for agent in agents:
            agent_agg = AggregatedMetrics(
                period_start=from_time,
                period_end=to_time,
                granularity=granularity,
                agent_type=agent["agent_type"],
                model=None,
                total_executions=agent["total_executions"],
                successful_executions=agent["successful_executions"],
                failed_executions=agent["failed_executions"],
                success_rate=agent["success_rate"],
                avg_duration_ms=agent["avg_duration_ms"],
                total_tokens=agent["total_tokens"],
                total_estimated_cost=agent["total_cost_usd"],
            )
            self.db.add(agent_agg)

        await self.db.flush()

        logger.info(
            "Created aggregated metrics",
            granularity=granularity,
            period_start=from_time.isoformat(),
            period_end=to_time.isoformat(),
            agent_count=len(agents) + 1,
        )

        return len(agents) + 1


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return MetricsCollector.get_instance()


async def get_metrics_service(db: AsyncSession) -> MetricsService:
    """
    FastAPI dependency for getting a MetricsService instance.

    Args:
        db: Database session

    Returns:
        Configured MetricsService instance
    """
    return MetricsService(db)
