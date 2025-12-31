"""
JWT Token Validation Middleware for FastAPI.

This middleware intercepts all incoming requests and:
1. Extracts JWT tokens from the Authorization header
2. Validates tokens against Supabase
3. Attaches user context to the request state for downstream handlers
4. Allows configurable public paths that bypass authentication

This provides request-level authentication verification independent of
route-level dependency injection, ensuring consistent security across
all API endpoints.
"""

import asyncio
import atexit
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# Thread pool for running synchronous Supabase calls without blocking the event loop
_jwt_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jwt-middleware-")

# Register cleanup handler for the thread pool
atexit.register(_jwt_executor.shutdown, wait=False)


# Paths that bypass token validation entirely (shared between middleware classes)
DEFAULT_PUBLIC_PATHS: set[str] = {
    "/",
    "/health",
    "/health/ready",
    "/health/live",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}

# Path prefixes that are considered public (e.g., static files)
DEFAULT_PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/_next/",
    "/static/",
)


def _is_public_path(
    path: str,
    public_paths: set[str] = DEFAULT_PUBLIC_PATHS,
    public_prefixes: tuple[str, ...] = DEFAULT_PUBLIC_PATH_PREFIXES,
) -> bool:
    """
    Check if the path should bypass authentication.

    Args:
        path: The request URL path
        public_paths: Set of exact paths that are public
        public_prefixes: Tuple of path prefixes that are public

    Returns:
        True if the path is public and should skip auth
    """
    if path in public_paths:
        return True

    for prefix in public_prefixes:
        if path.startswith(prefix):
            return True

    return False


def _extract_bearer_token(request: Request) -> str | None:
    """
    Extract JWT token from the Authorization header.

    Supports the standard Bearer token format:
    Authorization: Bearer <token>

    Args:
        request: The incoming HTTP request

    Returns:
        The extracted token, or None if not present or malformed
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.debug(
            "Invalid Authorization header format",
            header_parts=len(parts),
        )
        return None

    return parts[1]


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for JWT token validation and user context extraction.

    This middleware:
    - Extracts JWT tokens from the Authorization header
    - Validates tokens against Supabase (when configured)
    - Attaches authenticated user information to request.state.user
    - Skips authentication for configured public paths
    - Does NOT block requests - authentication errors are logged and
      the route handlers can decide how to proceed

    The middleware does not enforce authentication - it only validates
    and extracts user context when a token is present. Route-level
    dependencies (get_current_user) handle enforcement.

    Public paths (health checks, docs) are skipped entirely to avoid
    unnecessary token validation overhead.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Process the request through JWT validation.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response from downstream handlers
        """
        # Initialize user state to None
        request.state.user = None
        request.state.user_id = None
        request.state.auth_error = None

        # Skip validation for public paths
        if _is_public_path(request.url.path):
            return await call_next(request)

        # Extract and validate token if present
        token = _extract_bearer_token(request)
        if token:
            await self._validate_and_attach_user(request, token)

        return await call_next(request)

    async def _validate_and_attach_user(
        self, request: Request, token: str
    ) -> None:
        """
        Validate the JWT token and attach user info to request state.

        This method:
        1. Validates the token against Supabase
        2. On success, attaches user info to request.state.user
        3. On failure, logs the error and sets request.state.auth_error

        Args:
            request: The incoming HTTP request
            token: The JWT token to validate
        """
        try:
            # Import here to avoid circular imports
            from core.supabase import verify_jwt_token

            # Run synchronous Supabase call in thread pool
            loop = asyncio.get_running_loop()
            user_data = await loop.run_in_executor(
                _jwt_executor,
                partial(verify_jwt_token, token),
            )

            # Attach user data to request state
            request.state.user = user_data
            request.state.user_id = user_data.get("id")

            # Bind user context to structlog for this request
            structlog.contextvars.bind_contextvars(
                user_id=user_data.get("id"),
                user_email=user_data.get("email"),
            )

            logger.debug(
                "JWT validated successfully",
                user_id=user_data.get("id"),
            )

        except Exception as e:
            # Log the error but don't block the request
            # Route handlers will decide whether to require auth
            logger.warning(
                "JWT validation failed in middleware",
                error=str(e),
                error_type=type(e).__name__,
            )
            request.state.auth_error = str(e)


class StrictJWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Strict JWT middleware that blocks unauthenticated requests.

    Unlike JWTAuthMiddleware, this middleware returns 401 Unauthorized
    for any non-public request without a valid JWT token.

    Use this when you want to enforce authentication at the middleware
    level rather than at individual route handlers.

    WARNING: Only use this if you want ALL non-public endpoints to
    require authentication. For mixed public/private APIs, use the
    regular JWTAuthMiddleware with route-level dependencies.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with strict authentication enforcement."""
        from fastapi.responses import JSONResponse

        from core.middleware import get_error_response

        request.state.user = None
        request.state.user_id = None

        # Skip for public paths
        if _is_public_path(request.url.path):
            return await call_next(request)

        # Extract token
        token = _extract_bearer_token(request)
        if not token:
            logger.warning(
                "Strict auth: Missing authentication token",
                path=request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content=get_error_response(
                    status_code=401,
                    message="Authentication required",
                    code="AUTHENTICATION_REQUIRED",
                    request_id=getattr(request.state, "request_id", None),
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        try:
            from core.supabase import verify_jwt_token

            loop = asyncio.get_running_loop()
            user_data = await loop.run_in_executor(
                _jwt_executor,
                partial(verify_jwt_token, token),
            )

            request.state.user = user_data
            request.state.user_id = user_data.get("id")

            structlog.contextvars.bind_contextvars(
                user_id=user_data.get("id"),
                user_email=user_data.get("email"),
            )

            return await call_next(request)

        except Exception as e:
            logger.warning(
                "Strict auth: Token validation failed",
                error=str(e),
                path=request.url.path,
            )
            return JSONResponse(
                status_code=401,
                content=get_error_response(
                    status_code=401,
                    message="Invalid or expired token",
                    code="INVALID_TOKEN",
                    request_id=getattr(request.state, "request_id", None),
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )


def get_user_from_request(request: Request) -> dict[str, Any] | None:
    """
    Helper function to get authenticated user from request state.

    This is useful in route handlers that want to access user info
    set by the JWT middleware without using dependency injection.

    Args:
        request: The FastAPI request object

    Returns:
        User data dictionary if authenticated, None otherwise
    """
    return getattr(request.state, "user", None)


def get_user_id_from_request(request: Request) -> str | None:
    """
    Helper function to get user ID from request state.

    Args:
        request: The FastAPI request object

    Returns:
        User ID string if authenticated, None otherwise
    """
    return getattr(request.state, "user_id", None)
