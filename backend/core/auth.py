"""
Authentication dependencies for FastAPI route protection.

Provides FastAPI dependencies for:
- Extracting and validating JWT tokens from requests
- Injecting authenticated user context into endpoints
- Supporting both required and optional authentication
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError
from core.logging import get_logger
from core.supabase import verify_jwt_token

# Thread pool for running synchronous Supabase calls without blocking the event loop
_auth_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth-")

logger = get_logger(__name__)

# HTTP Bearer scheme for extracting JWT tokens
# auto_error=False allows us to handle missing tokens gracefully
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """
    Represents an authenticated user extracted from a valid JWT token.

    This dataclass is injected into FastAPI endpoints via dependency injection,
    providing type-safe access to user information.
    """

    id: UUID
    email: str | None
    role: str | None
    aud: str | None
    email_confirmed_at: str | None
    created_at: str | None
    updated_at: str | None
    app_metadata: dict[str, Any]
    user_metadata: dict[str, Any]

    @classmethod
    def from_token_data(cls, data: dict[str, Any]) -> "AuthenticatedUser":
        """
        Create an AuthenticatedUser from verified token data.

        Args:
            data: Dictionary containing user data from token verification

        Returns:
            AuthenticatedUser instance
        """
        return cls(
            id=UUID(data["id"]),
            email=data.get("email"),
            role=data.get("role"),
            aud=data.get("aud"),
            email_confirmed_at=data.get("email_confirmed_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            app_metadata=data.get("app_metadata", {}),
            user_metadata=data.get("user_metadata", {}),
        )

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return self.role == role

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a value from user metadata."""
        return self.user_metadata.get(key, default)

    def get_app_metadata(self, key: str, default: Any = None) -> Any:
        """Get a value from app metadata."""
        return self.app_metadata.get(key, default)


async def _extract_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str | None:
    """
    Extract JWT token from request.

    Supports both:
    - Standard Authorization: Bearer <token> header (via HTTPBearer scheme)
    - Direct Authorization header parsing for edge cases

    Args:
        credentials: Credentials from HTTPBearer scheme
        authorization: Raw Authorization header value

    Returns:
        The extracted JWT token, or None if not present
    """
    # First try the HTTPBearer credentials
    if credentials and credentials.credentials:
        return credentials.credentials

    # Fall back to manual header parsing for edge cases
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]

    return None


async def _verify_token_async(token: str) -> dict[str, Any]:
    """
    Verify JWT token asynchronously by running the sync Supabase call in a thread pool.

    This prevents blocking the FastAPI event loop during token verification.

    Args:
        token: The JWT access token to verify

    Returns:
        Dictionary containing user information from the token

    Raises:
        Exception: Any exception from verify_jwt_token is propagated
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_auth_executor, partial(verify_jwt_token, token))


async def get_current_user(
    token: str | None = Depends(_extract_token),
) -> AuthenticatedUser:
    """
    FastAPI dependency that requires authentication.

    Extracts the JWT token from the request, validates it against Supabase,
    and returns the authenticated user. Raises AuthenticationError if
    the token is missing or invalid.

    Usage:
        @router.get("/protected")
        async def protected_endpoint(
            user: AuthenticatedUser = Depends(get_current_user),
        ):
            return {"user_id": str(user.id)}

    Args:
        token: JWT token extracted from request headers

    Returns:
        AuthenticatedUser instance for the authenticated user

    Raises:
        AuthenticationError: If token is missing or invalid
    """
    if not token:
        logger.warning("Authentication required but no token provided")
        raise AuthenticationError("Authentication required")

    try:
        user_data = await _verify_token_async(token)
        user = AuthenticatedUser.from_token_data(user_data)
        logger.debug(
            "User authenticated",
            user_id=str(user.id),
            email=user.email,
        )
        return user
    except AuthenticationError:
        raise
    except Exception as e:
        logger.warning(
            "Token validation failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise AuthenticationError(f"Invalid or expired token: {e}")


async def get_optional_user(
    token: str | None = Depends(_extract_token),
) -> AuthenticatedUser | None:
    """
    FastAPI dependency for optional authentication.

    Similar to get_current_user, but returns None instead of raising
    an error when no token is provided. Still validates the token if present.

    Usage:
        @router.get("/public-or-private")
        async def endpoint(
            user: AuthenticatedUser | None = Depends(get_optional_user),
        ):
            if user:
                return {"authenticated": True, "user_id": str(user.id)}
            return {"authenticated": False}

    Args:
        token: JWT token extracted from request headers

    Returns:
        AuthenticatedUser instance if authenticated, None otherwise

    Raises:
        AuthenticationError: If token is present but invalid
    """
    if not token:
        return None

    try:
        user_data = await _verify_token_async(token)
        user = AuthenticatedUser.from_token_data(user_data)
        logger.debug(
            "User authenticated (optional)",
            user_id=str(user.id),
            email=user.email,
        )
        return user
    except Exception as e:
        logger.warning(
            "Optional token validation failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise AuthenticationError(f"Invalid or expired token: {e}")


def require_role(required_role: str):
    """
    Factory function that creates a dependency requiring a specific role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            user: AuthenticatedUser = Depends(require_role("admin")),
        ):
            return {"admin_user": str(user.id)}

    Args:
        required_role: The role that the user must have

    Returns:
        A FastAPI dependency function
    """

    async def role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user.has_role(required_role):
            logger.warning(
                "Authorization denied - missing role",
                user_id=str(user.id),
                required_role=required_role,
                user_role=user.role,
            )
            raise AuthorizationError(
                f"Required role '{required_role}' not found"
            )
        return user

    return role_checker


# Type aliases for cleaner endpoint signatures
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]


# Development mode helper for bypassing auth
async def get_dev_user() -> AuthenticatedUser:
    """
    Development-only dependency that provides a mock user.

    Only available when settings.is_development is True.
    For production, always use get_current_user.

    Usage:
        @router.get("/dev-endpoint")
        async def dev_endpoint(
            user: AuthenticatedUser = Depends(get_dev_user),
        ):
            return {"dev_user": str(user.id)}

    Returns:
        A mock AuthenticatedUser for development

    Raises:
        AuthenticationError: If not in development mode
    """
    if not settings.is_development:
        raise AuthenticationError(
            "Development authentication is not available in this environment"
        )

    logger.warning("Using development mock user - DO NOT USE IN PRODUCTION")
    return AuthenticatedUser(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        email="dev@example.com",
        role="authenticated",
        aud="authenticated",
        email_confirmed_at=None,
        created_at=None,
        updated_at=None,
        app_metadata={},
        user_metadata={"name": "Development User"},
    )
