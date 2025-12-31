"""
Distributed tracing infrastructure for request tracking and observability.

Provides:
- Trace ID generation and propagation
- Span creation and management
- Context propagation across service boundaries
- Integration with structlog for correlated logging
"""

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import structlog

from core.logging import get_logger

logger = get_logger(__name__)


class SpanKind(str, Enum):
    """Types of spans for categorization."""

    SERVER = "server"  # Incoming HTTP request
    CLIENT = "client"  # Outgoing HTTP request
    INTERNAL = "internal"  # Internal operation
    PRODUCER = "producer"  # Message producer
    CONSUMER = "consumer"  # Message consumer


class SpanStatus(str, Enum):
    """Status of a span execution."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanContext:
    """
    Context for trace propagation.

    Follows W3C Trace Context format for cross-service propagation.
    """

    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    sampled: bool = True

    def to_traceparent(self) -> str:
        """Generate W3C traceparent header value."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    @classmethod
    def from_traceparent(cls, traceparent: str) -> Optional["SpanContext"]:
        """Parse W3C traceparent header value."""
        try:
            parts = traceparent.split("-")
            if len(parts) != 4 or parts[0] != "00":
                return None

            return cls(
                trace_id=parts[1],
                span_id=parts[2],
                sampled=parts[3] == "01",
            )
        except Exception:
            return None


@dataclass
class Span:
    """
    Represents a single unit of work in a distributed trace.

    Captures timing, attributes, and hierarchical relationships.
    """

    name: str
    context: SpanContext
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate span duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        """Set multiple span attributes."""
        self.attributes.update(attributes)

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_status(self, status: SpanStatus, description: Optional[str] = None) -> None:
        """Set the span status."""
        self.status = status
        if description:
            self.set_attribute("status_description", description)

    def end(self, status: Optional[SpanStatus] = None) -> None:
        """End the span and record end time."""
        self.end_time = datetime.now(timezone.utc)
        if status:
            self.status = status
        elif self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def to_dict(self) -> dict[str, Any]:
        """Convert span to dictionary for serialization."""
        return {
            "name": self.name,
            "trace_id": self.context.trace_id,
            "span_id": self.context.span_id,
            "parent_span_id": self.context.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


# Context variables for trace propagation
_current_trace_context: ContextVar[Optional[SpanContext]] = ContextVar(
    "current_trace_context", default=None
)
_current_span: ContextVar[Optional[Span]] = ContextVar("current_span", default=None)


def generate_trace_id() -> str:
    """Generate a new trace ID (32-character hex string)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a new span ID (16-character hex string)."""
    return uuid.uuid4().hex[:16]


def get_current_trace_context() -> Optional[SpanContext]:
    """Get the current trace context from context variables."""
    return _current_trace_context.get()


def set_current_trace_context(context: Optional[SpanContext]) -> None:
    """Set the current trace context in context variables."""
    _current_trace_context.set(context)

    # Also bind to structlog for correlated logging
    if context:
        structlog.contextvars.bind_contextvars(
            trace_id=context.trace_id,
            span_id=context.span_id,
        )


def get_current_span() -> Optional[Span]:
    """Get the current active span."""
    return _current_span.get()


def set_current_span(span: Optional[Span]) -> None:
    """Set the current active span."""
    _current_span.set(span)


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID if available."""
    context = get_current_trace_context()
    return context.trace_id if context else None


class TraceContext:
    """
    Context manager for creating and managing spans.

    Usage:
        with TraceContext("operation_name", kind=SpanKind.INTERNAL) as span:
            span.set_attribute("key", "value")
            # ... do work ...
    """

    def __init__(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[dict[str, Any]] = None,
        parent_context: Optional[SpanContext] = None,
    ):
        self.name = name
        self.kind = kind
        self.attributes = attributes or {}
        self.parent_context = parent_context
        self.span: Optional[Span] = None
        self._previous_span: Optional[Span] = None

    def __enter__(self) -> Span:
        # Get or create trace context
        parent = self.parent_context or get_current_trace_context()

        if parent:
            # Create child span
            context = SpanContext(
                trace_id=parent.trace_id,
                span_id=generate_span_id(),
                parent_span_id=parent.span_id,
                sampled=parent.sampled,
            )
        else:
            # Create new trace
            context = SpanContext(
                trace_id=generate_trace_id(),
                span_id=generate_span_id(),
            )

        self.span = Span(
            name=self.name,
            context=context,
            kind=self.kind,
            attributes=self.attributes,
        )

        # Save previous span and set current
        self._previous_span = get_current_span()
        set_current_span(self.span)
        set_current_trace_context(context)

        logger.debug(
            "Span started",
            span_name=self.name,
            trace_id=context.trace_id,
            span_id=context.span_id,
            parent_span_id=context.parent_span_id,
        )

        return self.span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.span:
            if exc_type:
                self.span.set_status(SpanStatus.ERROR, str(exc_val))
                self.span.set_attribute("error.type", exc_type.__name__)
                self.span.set_attribute("error.message", str(exc_val))
            else:
                self.span.set_status(SpanStatus.OK)

            self.span.end()

            # Collect the span
            from core.trace_collector import get_trace_collector
            collector = get_trace_collector()
            collector.collect(self.span)

            logger.debug(
                "Span ended",
                span_name=self.name,
                duration_ms=self.span.duration_ms,
                status=self.span.status.value,
            )

        # Restore previous span
        set_current_span(self._previous_span)
        if self._previous_span:
            set_current_trace_context(self._previous_span.context)


def extract_trace_context(headers: dict[str, str]) -> Optional[SpanContext]:
    """
    Extract trace context from HTTP headers.

    Supports:
    - W3C Trace Context (traceparent header)
    - X-Trace-ID custom header (fallback)
    """
    # Try W3C traceparent first
    traceparent = headers.get("traceparent")
    if traceparent:
        context = SpanContext.from_traceparent(traceparent)
        if context:
            return context

    # Fallback to custom header
    trace_id = headers.get("x-trace-id") or headers.get("X-Trace-ID")
    if trace_id:
        return SpanContext(
            trace_id=trace_id,
            span_id=generate_span_id(),
        )

    return None


def inject_trace_context(headers: dict[str, str], context: Optional[SpanContext] = None) -> None:
    """
    Inject trace context into HTTP headers for propagation.
    """
    ctx = context or get_current_trace_context()
    if ctx:
        headers["traceparent"] = ctx.to_traceparent()
        headers["X-Trace-ID"] = ctx.trace_id


def create_trace_headers(context: Optional[SpanContext] = None) -> dict[str, str]:
    """
    Create trace headers dictionary for outgoing requests.
    """
    headers: dict[str, str] = {}
    inject_trace_context(headers, context)
    return headers
