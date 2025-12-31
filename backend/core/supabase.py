"""
Supabase client initialization and management.

Provides async-compatible Supabase client for authentication verification,
token validation, and user context extraction.
"""

from typing import Any

from supabase import Client, create_client

from core.config import settings
from core.exceptions import ConfigurationError, ExternalServiceError
from core.logging import get_logger

logger = get_logger(__name__)

# Module-level state for lazy initialization
_supabase_client: Client | None = None
_supabase_admin_client: Client | None = None


def _validate_supabase_config() -> None:
    """
    Validate that required Supabase configuration is present.

    Raises:
        ConfigurationError: If required Supabase settings are missing
    """
    if not settings.supabase_url:
        raise ConfigurationError(
            "SUPABASE_URL is not configured",
            details={"required_env_var": "SUPABASE_URL"},
        )
    if not settings.supabase_anon_key.get_secret_value():
        raise ConfigurationError(
            "SUPABASE_ANON_KEY is not configured",
            details={"required_env_var": "SUPABASE_ANON_KEY"},
        )


def get_supabase_client() -> Client:
    """
    Get or create the Supabase client (lazy initialization).

    Uses the anonymous/public key for client-side operations.
    This client respects Row Level Security (RLS) policies.

    Returns:
        The global Supabase Client instance.

    Raises:
        ConfigurationError: If Supabase configuration is missing
    """
    global _supabase_client
    if _supabase_client is None:
        _validate_supabase_config()
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key.get_secret_value(),
        )
        logger.info("Supabase client initialized", url=settings.supabase_url)
    return _supabase_client


def get_supabase_admin_client() -> Client:
    """
    Get or create the Supabase admin client (lazy initialization).

    Uses the service role key for admin operations.
    This client bypasses Row Level Security (RLS) policies.
    Use with caution - only for trusted server-side operations.

    Returns:
        The global Supabase Admin Client instance.

    Raises:
        ConfigurationError: If Supabase configuration is missing
    """
    global _supabase_admin_client
    if _supabase_admin_client is None:
        _validate_supabase_config()
        if not settings.supabase_service_role_key.get_secret_value():
            raise ConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY is not configured",
                details={"required_env_var": "SUPABASE_SERVICE_ROLE_KEY"},
            )
        _supabase_admin_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key.get_secret_value(),
        )
        logger.info("Supabase admin client initialized", url=settings.supabase_url)
    return _supabase_admin_client


def _extract_user_data(user: Any) -> dict[str, Any]:
    """
    Extract user data from a Supabase User object into a dictionary.

    This helper function centralizes user data extraction to avoid duplication.

    Args:
        user: The Supabase User object (from gotrue)

    Returns:
        Dictionary containing user information
    """
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "aud": user.aud,
        "email_confirmed_at": (
            user.email_confirmed_at.isoformat() if user.email_confirmed_at else None
        ),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "app_metadata": user.app_metadata or {},
        "user_metadata": user.user_metadata or {},
    }


def verify_jwt_token(token: str) -> dict[str, Any]:
    """
    Verify a JWT token against Supabase and extract user information.

    Note: This function is synchronous because the Supabase Python client
    uses synchronous HTTP calls internally. The async wrapper in auth.py
    ensures it doesn't block the event loop in FastAPI.

    Args:
        token: The JWT access token from the Authorization header

    Returns:
        Dictionary containing user information from the token

    Raises:
        ExternalServiceError: If token verification fails
    """
    try:
        client = get_supabase_client()
        # Use Supabase's auth.get_user to verify the token
        # This validates the token and returns user info
        response = client.auth.get_user(token)

        if response is None or response.user is None:
            raise ExternalServiceError(
                service="Supabase",
                message="Invalid or expired token",
                details={"reason": "Token verification returned no user"},
            )

        return _extract_user_data(response.user)
    except ExternalServiceError:
        raise
    except Exception as e:
        logger.error(
            "Token verification failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ExternalServiceError(
            service="Supabase",
            message="Token verification failed",
            details={"error": str(e)},
        )


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """
    Get user information by user ID using admin privileges.

    Args:
        user_id: The Supabase auth user ID

    Returns:
        Dictionary containing user information, or None if not found

    Raises:
        ExternalServiceError: If the operation fails
    """
    try:
        admin_client = get_supabase_admin_client()
        response = admin_client.auth.admin.get_user_by_id(user_id)

        if response is None or response.user is None:
            return None

        return _extract_user_data(response.user)
    except Exception as e:
        logger.error(
            "Failed to get user by ID",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ExternalServiceError(
            service="Supabase",
            message="Failed to get user information",
            details={"user_id": user_id, "error": str(e)},
        )


def reset_clients() -> None:
    """
    Reset the Supabase clients.

    Useful for testing or when configuration changes.
    """
    global _supabase_client, _supabase_admin_client
    _supabase_client = None
    _supabase_admin_client = None
    logger.info("Supabase clients reset")
