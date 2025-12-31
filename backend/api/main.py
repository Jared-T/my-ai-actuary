"""
FastAPI application entry point.

This module creates and configures the main FastAPI application with:
- CORS middleware for frontend communication
- Custom middleware for logging and request tracking
- Exception handlers for consistent error responses
- Health check endpoints
- API router mounting
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import agents, audit_trail, backup, cli_tasks, conversations, health, knowledge_base, metrics, orchestration, tracing, workflows
from core.config import settings
from core.database import close_db
from core.exceptions import AppError, AuthenticationError, AuthorizationError
from core.logging import configure_logging, get_logger
from core.jwt_middleware import JWTAuthMiddleware
from core.middleware import (
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RequestContextMiddleware,
    get_error_response,
)
from core.tracing_middleware import TracingMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events for the application.
    Use this for initializing and cleaning up resources like
    database connections, caches, etc.
    """
    # Startup
    configure_logging()
    logger.info(
        "Application starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    yield

    # Shutdown
    logger.info("Application shutting down")
    await close_db()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered actuarial assistant backend",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Configure middleware (order matters - last added is first executed)
    configure_middleware(app)

    # Configure exception handlers
    configure_exception_handlers(app)

    # Include routers
    configure_routes(app)

    return app


def configure_middleware(app: FastAPI) -> None:
    """Configure application middleware."""
    # CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time", "X-Trace-ID", "traceparent"],
    )

    # Custom middleware (order: last added = first executed)
    # Execution order: RequestContext -> JWT Auth -> Tracing -> Logging -> ErrorHandling
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TracingMiddleware)  # Tracing after request context
    app.add_middleware(JWTAuthMiddleware)  # JWT validation after request context
    app.add_middleware(RequestContextMiddleware)


def configure_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        """Handle authentication errors with 401 status."""
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Authentication error",
            error_code=exc.code,
            error_message=exc.message,
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=get_error_response(
                status_code=401,
                message=exc.message,
                code=exc.code,
                request_id=request_id,
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        """Handle authorization errors with 403 status."""
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "Authorization error",
            error_code=exc.code,
            error_message=exc.message,
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=get_error_response(
                status_code=403,
                message=exc.message,
                code=exc.code,
                request_id=request_id,
            ),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle custom application errors."""
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "Application error",
            error_code=exc.code,
            error_message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=get_error_response(
                status_code=400,
                message=exc.message,
                code=exc.code,
                request_id=request_id,
                details=exc.details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions with structured response."""
        request_id = getattr(request.state, "request_id", None)

        # If detail is already structured, use it; otherwise wrap it
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            content = exc.detail
            if request_id:
                content["error"]["request_id"] = request_id
        else:
            content = get_error_response(
                status_code=exc.status_code,
                message=str(exc.detail),
                code="HTTP_ERROR",
                request_id=request_id,
            )

        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled exceptions - ensures no silent failures."""
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
        )

        # In production, don't expose internal error details
        message = (
            str(exc) if settings.is_development else "An internal error occurred"
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=get_error_response(
                status_code=500,
                message=message,
                code="INTERNAL_ERROR",
                request_id=request_id,
            ),
        )


def configure_routes(app: FastAPI) -> None:
    """Configure API routes."""
    # Health check endpoints
    app.include_router(health.router, tags=["Health"])

    # Agent endpoints
    app.include_router(agents.router)

    # Orchestration endpoints (intelligent routing and handoffs)
    app.include_router(orchestration.router)

    # Backup and recovery endpoints
    app.include_router(backup.router)
    app.include_router(backup.recovery_router)

    # Tracing and audit endpoints
    app.include_router(tracing.router)

    # Comprehensive audit trail system (artifact hashing, compliance reporting)
    app.include_router(audit_trail.router)

    # Workflow definition endpoints
    app.include_router(workflows.router)

    # CLI Task endpoints (Codex CLI integration)
    app.include_router(cli_tasks.router)
    app.include_router(cli_tasks.batch_router)

    # Knowledge Base endpoints (actuarial methods, templates, precedents)
    app.include_router(knowledge_base.router)

    # Metrics endpoints (agent performance monitoring)
    app.include_router(metrics.router)

    # Conversation history endpoints
    app.include_router(conversations.router)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        """Root endpoint returning API information."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs" if settings.is_development else None,
        }


# Create the application instance
app = create_app()
