"""
Health check endpoints for monitoring and orchestration.

Provides endpoints for:
- /health - Basic health check
- /health/ready - Readiness probe (checks external dependencies)
- /health/live - Liveness probe (basic alive check)
- /health/auth - Authentication status check (shows JWT middleware status)
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request, status

from core.config import settings
from core.jwt_middleware import get_user_from_request, get_user_id_from_request

router = APIRouter()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Basic health check endpoint returning application status",
)
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.

    Returns application name, version, environment, and current timestamp.
    Use this for basic monitoring and load balancer health checks.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Check if the application is ready to handle traffic",
)
async def readiness_check() -> dict[str, Any]:
    """
    Readiness probe for Kubernetes or similar orchestration.

    Checks that the application and its dependencies are ready
    to handle incoming requests. Returns 503 if not ready.

    Currently checks:
    - Application is running

    Future checks to add:
    - Database connection
    - OpenAI API reachability
    - Supabase connection
    """
    checks: dict[str, dict[str, Any]] = {
        "application": {
            "status": "healthy",
            "message": "Application is running",
        },
    }

    # TODO: Add dependency checks when services are implemented
    # - Database connectivity
    # - OpenAI API reachability
    # - Supabase connection

    all_healthy = all(check["status"] == "healthy" for check in checks.values())

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Check if the application is alive",
)
async def liveness_check() -> dict[str, str]:
    """
    Liveness probe for Kubernetes or similar orchestration.

    Simple check that the application process is alive and responding.
    Unlike readiness, this doesn't check external dependencies.

    If this fails, the container should be restarted.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/auth",
    status_code=status.HTTP_200_OK,
    summary="Authentication status",
    description="Check JWT middleware authentication status for the current request",
)
async def auth_status_check(request: Request) -> dict[str, Any]:
    """
    Authentication status endpoint for verifying JWT middleware.

    Returns information about the current request's authentication state:
    - Whether a valid JWT token was provided
    - User information if authenticated
    - Any authentication errors if token validation failed

    This endpoint is useful for:
    - Verifying JWT middleware is working correctly
    - Debugging authentication issues
    - Frontend applications checking auth state
    """
    user = get_user_from_request(request)
    user_id = get_user_id_from_request(request)
    auth_error = getattr(request.state, "auth_error", None)

    if user:
        return {
            "authenticated": True,
            "user_id": user_id,
            "email": user.get("email"),
            "role": user.get("role"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        return {
            "authenticated": False,
            "user_id": None,
            "error": auth_error,
            "message": "No valid authentication token provided" if not auth_error else "Token validation failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
