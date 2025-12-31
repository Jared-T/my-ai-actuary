"""
FastAPI middleware for request processing.

Includes middleware for:
- Request ID tracking
- Request/response logging
- Error handling
- Performance monitoring
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context for logging and tracing.

    Adds a unique request ID to each request and binds it to the
    structlog context for consistent request tracing.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Add request ID to request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.

    Logs request start, completion, and timing information.
    Excludes health check endpoints from logging to reduce noise.
    """

    # Paths to exclude from logging
    EXCLUDED_PATHS: set[str] = {"/health", "/health/ready", "/health/live", "/favicon.ico"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        start_time = time.perf_counter()

        # Log request start in debug mode
        if settings.debug:
            logger.debug(
                "Request started",
                client_host=request.client.host if request.client else None,
                query_params=dict(request.query_params),
            )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log successful response
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add timing header
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log error
            logger.error(
                "Request failed",
                error=str(exc),
                error_type=type(exc).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Catches unhandled exceptions and returns structured error responses.
    Ensures no silent failures as per project guidelines.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            # Log the error with full context
            logger.exception(
                "Unhandled exception",
                error=str(exc),
                error_type=type(exc).__name__,
            )

            # Re-raise to let FastAPI's exception handlers deal with it
            # This follows the project's "no silent failures" policy
            raise


def get_error_response(
    status_code: int,
    message: str,
    code: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a structured error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        code: Machine-readable error code
        request_id: Request ID for tracing
        details: Additional error details

    Returns:
        Structured error response dictionary
    """
    response: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status_code": status_code,
        }
    }

    if request_id:
        response["error"]["request_id"] = request_id

    if details:
        response["error"]["details"] = details

    return response
