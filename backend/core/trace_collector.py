"""
Trace collector for aggregating and storing trace data.

Provides:
- In-memory trace buffering
- Trace export to database
- Trace querying and retrieval
- Trace statistics and monitoring
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.tracing import Span, SpanKind, SpanStatus

logger = get_logger(__name__)

# Maximum number of spans to keep in memory buffer
MAX_BUFFER_SIZE = 10000

# Maximum age of spans to keep in memory (in seconds)
MAX_SPAN_AGE_SECONDS = 3600  # 1 hour


class TraceCollector:
    """
    Collects and manages trace spans.

    Provides in-memory buffering with periodic export to database.
    Supports querying for recent traces and monitoring.
    """

    _instance: Optional["TraceCollector"] = None

    def __init__(self) -> None:
        """Initialize the trace collector."""
        self._buffer: deque[Span] = deque(maxlen=MAX_BUFFER_SIZE)
        self._traces: dict[str, list[Span]] = {}  # trace_id -> spans
        self._export_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "TraceCollector":
        """Get or create the singleton trace collector instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def collect(self, span: Span) -> None:
        """
        Collect a completed span.

        Args:
            span: The span to collect
        """
        self._buffer.append(span)

        # Group by trace_id for easy retrieval
        trace_id = span.context.trace_id
        if trace_id not in self._traces:
            self._traces[trace_id] = []
        self._traces[trace_id].append(span)

        logger.debug(
            "Span collected",
            trace_id=trace_id,
            span_name=span.name,
            span_id=span.context.span_id,
        )

    def get_trace(self, trace_id: str) -> list[Span]:
        """
        Get all spans for a specific trace.

        Args:
            trace_id: The trace ID to retrieve

        Returns:
            List of spans in the trace
        """
        return self._traces.get(trace_id, [])

    def get_recent_traces(
        self,
        limit: int = 100,
        kind: Optional[SpanKind] = None,
        status: Optional[SpanStatus] = None,
        min_duration_ms: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent traces with optional filtering.

        Args:
            limit: Maximum number of traces to return
            kind: Filter by span kind
            status: Filter by span status
            min_duration_ms: Filter by minimum duration

        Returns:
            List of trace summaries
        """
        traces: dict[str, dict[str, Any]] = {}

        # Iterate from end of deque without creating a full copy
        # Use negative indexing for efficient reverse iteration
        for i in range(len(self._buffer) - 1, -1, -1):
            if len(traces) >= limit:
                break
            span = self._buffer[i]

            trace_id = span.context.trace_id

            # Apply filters
            if kind and span.kind != kind:
                continue
            if status and span.status != status:
                continue
            if min_duration_ms and span.duration_ms and span.duration_ms < min_duration_ms:
                continue

            if trace_id not in traces:
                traces[trace_id] = {
                    "trace_id": trace_id,
                    "root_span": None,
                    "span_count": 0,
                    "start_time": None,
                    "end_time": None,
                    "duration_ms": None,
                    "status": SpanStatus.OK.value,
                    "has_errors": False,
                }

            traces[trace_id]["span_count"] += 1

            # Track root span (no parent)
            if span.context.parent_span_id is None:
                traces[trace_id]["root_span"] = span.name
                traces[trace_id]["start_time"] = span.start_time.isoformat()
                if span.end_time:
                    traces[trace_id]["end_time"] = span.end_time.isoformat()
                traces[trace_id]["duration_ms"] = span.duration_ms

            # Track error status
            if span.status == SpanStatus.ERROR:
                traces[trace_id]["has_errors"] = True
                traces[trace_id]["status"] = SpanStatus.ERROR.value

        return list(traces.values())

    def get_trace_details(self, trace_id: str) -> Optional[dict[str, Any]]:
        """
        Get detailed information about a specific trace.

        Args:
            trace_id: The trace ID

        Returns:
            Detailed trace information or None if not found
        """
        spans = self.get_trace(trace_id)
        if not spans:
            return None

        # Sort spans by start time
        sorted_spans = sorted(spans, key=lambda s: s.start_time)

        # Find root span
        root_span = next(
            (s for s in sorted_spans if s.context.parent_span_id is None),
            sorted_spans[0] if sorted_spans else None,
        )

        return {
            "trace_id": trace_id,
            "root_span": root_span.to_dict() if root_span else None,
            "spans": [s.to_dict() for s in sorted_spans],
            "span_count": len(spans),
            "start_time": sorted_spans[0].start_time.isoformat() if sorted_spans else None,
            "end_time": sorted_spans[-1].end_time.isoformat()
            if sorted_spans and sorted_spans[-1].end_time
            else None,
            "total_duration_ms": root_span.duration_ms if root_span else None,
            "has_errors": any(s.status == SpanStatus.ERROR for s in spans),
        }

    def get_statistics(self) -> dict[str, Any]:
        """
        Get trace collector statistics.

        Returns:
            Dictionary with collector statistics
        """
        total_spans = len(self._buffer)
        total_traces = len(self._traces)

        # Calculate status distribution
        status_counts: dict[str, int] = {}
        kind_counts: dict[str, int] = {}
        total_duration = 0.0
        span_with_duration = 0

        for span in self._buffer:
            status_counts[span.status.value] = status_counts.get(span.status.value, 0) + 1
            kind_counts[span.kind.value] = kind_counts.get(span.kind.value, 0) + 1

            if span.duration_ms:
                total_duration += span.duration_ms
                span_with_duration += 1

        avg_duration = total_duration / span_with_duration if span_with_duration > 0 else 0

        return {
            "total_spans": total_spans,
            "total_traces": total_traces,
            "buffer_capacity": MAX_BUFFER_SIZE,
            "buffer_usage_percent": (total_spans / MAX_BUFFER_SIZE) * 100 if MAX_BUFFER_SIZE > 0 else 0,
            "status_distribution": status_counts,
            "kind_distribution": kind_counts,
            "average_duration_ms": round(avg_duration, 2),
        }

    def cleanup_old_traces(self, max_age_seconds: int = MAX_SPAN_AGE_SECONDS) -> int:
        """
        Clean up old traces from memory.

        Args:
            max_age_seconds: Maximum age in seconds for traces to keep

        Returns:
            Number of traces removed
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        removed_count = 0

        # Find traces to remove
        traces_to_remove = []
        for trace_id, spans in self._traces.items():
            # Check if all spans in trace are old
            if all(s.end_time and s.end_time < cutoff_time for s in spans):
                traces_to_remove.append(trace_id)

        # Remove old traces
        for trace_id in traces_to_remove:
            del self._traces[trace_id]
            removed_count += 1

        if removed_count > 0:
            logger.info(
                "Cleaned up old traces",
                removed_count=removed_count,
                remaining_traces=len(self._traces),
            )

        return removed_count

    async def export_to_database(self, db: AsyncSession) -> int:
        """
        Export collected spans to the database.

        Args:
            db: Database session

        Returns:
            Number of spans exported
        """
        async with self._export_lock:
            from models.trace import TraceSpan

            spans_to_export = list(self._buffer)
            if not spans_to_export:
                return 0

            # Create database records
            db_spans = []
            for span in spans_to_export:
                db_span = TraceSpan(
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
                )
                db_spans.append(db_span)

            db.add_all(db_spans)
            await db.flush()

            logger.info(
                "Exported spans to database",
                span_count=len(db_spans),
            )

            return len(db_spans)

    def clear(self) -> None:
        """Clear all collected spans (useful for testing)."""
        self._buffer.clear()
        self._traces.clear()


# Global singleton getter
def get_trace_collector() -> TraceCollector:
    """Get the global trace collector instance."""
    return TraceCollector.get_instance()
