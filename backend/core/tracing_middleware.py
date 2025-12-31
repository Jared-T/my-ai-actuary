"""
Tracing middleware for automatic span creation on HTTP requests.

Provides:
- Automatic trace context extraction/injection
- Request span creation with timing
- Error tracking and status propagation
- Integration with existing request context middleware
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.tracing import (
    SpanContext,
    SpanKind,
    SpanStatus,
    TraceContext,
    extract_trace_context,
    generate_span_id,
    generate_trace_id,
    get_current_trace_context,
    set_current_trace_context,
)

logger = structlog.get_logger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for distributed tracing of HTTP requests.

    Creates spans for each incoming request and propagates trace context
    to downstream services via response headers.
    """

    # Paths to exclude from tracing
    EXCLUDED_PATHS: set[str] = {
        "/health",
        "/health/ready",
        "/health/live",
        "/favicon.ico",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Process the request with tracing.

        Creates a span for the request lifecycle and propagates trace context.
        """
        # Skip tracing for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Extract trace context from incoming headers
        headers = dict(request.headers)
        parent_context = extract_trace_context(headers)

        # Create or continue trace
        if parent_context:
            # Continue existing trace with new span
            span_context = SpanContext(
                trace_id=parent_context.trace_id,
                span_id=generate_span_id(),
                parent_span_id=parent_context.span_id,
                sampled=parent_context.sampled,
            )
        else:
            # Create new trace
            span_context = SpanContext(
                trace_id=generate_trace_id(),
                span_id=generate_span_id(),
            )

        # Set trace context for this request
        set_current_trace_context(span_context)

        # Bind trace context to structlog
        structlog.contextvars.bind_contextvars(
            trace_id=span_context.trace_id,
            span_id=span_context.span_id,
        )

        # Create span name from method and path
        span_name = f"{request.method} {request.url.path}"

        # Build request attributes
        request_attributes = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.path": request.url.path,
            "http.scheme": request.url.scheme,
            "http.host": request.url.hostname,
            "http.user_agent": request.headers.get("user-agent", ""),
            "http.client_ip": request.client.host if request.client else None,
        }

        # Add query params if present
        if request.query_params:
            request_attributes["http.query_params"] = dict(request.query_params)

        start_time = time.perf_counter()

        with TraceContext(
            name=span_name,
            kind=SpanKind.SERVER,
            attributes=request_attributes,
            parent_context=parent_context,
        ) as span:
            try:
                # Store trace info on request state for access in handlers
                request.state.trace_id = span_context.trace_id
                request.state.span_id = span_context.span_id

                # Process request
                response = await call_next(request)

                # Calculate duration
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Add response attributes
                span.set_attributes({
                    "http.status_code": response.status_code,
                    "http.response_time_ms": round(duration_ms, 2),
                })

                # Set status based on HTTP status code
                if response.status_code >= 500:
                    span.set_status(SpanStatus.ERROR, f"HTTP {response.status_code}")
                elif response.status_code >= 400:
                    span.set_status(SpanStatus.OK)  # Client errors are not server errors
                else:
                    span.set_status(SpanStatus.OK)

                # Add trace headers to response
                response.headers["X-Trace-ID"] = span_context.trace_id
                response.headers["traceparent"] = span_context.to_traceparent()

                return response

            except Exception as exc:
                # Calculate duration for error case
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Add error attributes
                span.set_attributes({
                    "error": True,
                    "error.type": type(exc).__name__,
                    "error.message": str(exc),
                    "http.response_time_ms": round(duration_ms, 2),
                })

                span.add_event(
                    "exception",
                    {
                        "exception.type": type(exc).__name__,
                        "exception.message": str(exc),
                    },
                )

                span.set_status(SpanStatus.ERROR, str(exc))

                # Re-raise to let error handling middleware deal with it
                raise


class TraceResponseHeaderMiddleware(BaseHTTPMiddleware):
    """
    Simple middleware to ensure trace headers are always present in responses.

    This is a fallback in case TracingMiddleware is not active or fails.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # Add trace ID from request state if available and not already set
        if hasattr(request.state, "trace_id") and "X-Trace-ID" not in response.headers:
            response.headers["X-Trace-ID"] = request.state.trace_id

        return response


def get_trace_context_from_request(request: Request) -> dict[str, Any]:
    """
    Get trace context information from a request.

    Utility function for accessing trace data in route handlers.

    Args:
        request: The FastAPI request object

    Returns:
        Dictionary with trace context information
    """
    context = get_current_trace_context()

    return {
        "trace_id": getattr(request.state, "trace_id", None) or (context.trace_id if context else None),
        "span_id": getattr(request.state, "span_id", None) or (context.span_id if context else None),
        "request_id": getattr(request.state, "request_id", None),
    }
