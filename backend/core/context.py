"""
User and request context management for dependency injection.

Provides comprehensive context objects that flow through the request lifecycle:
- UserContext: User identity, permissions, and metadata
- RequestContext: Request-scoped context combining user, request info, and database session

This module enables proper authorization by making user context available
throughout the entire request lifecycle without explicit parameter passing.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import AuthenticatedUser
from core.exceptions import AuthorizationError

logger = structlog.get_logger(__name__)


# Metadata key constants for consistent access across the codebase
class MetadataKeys:
    """Constants for metadata dictionary keys."""

    PERMISSIONS = "permissions"
    ROLES = "roles"
    TENANT_ID = "tenant_id"
    SUBSCRIPTION_TIER = "subscription_tier"
    FEATURE_FLAGS = "feature_flags"


# Default values
DEFAULT_SUBSCRIPTION_TIER = "free"


# Context variables for request-scoped data
_user_context_var: ContextVar["UserContext | None"] = ContextVar("user_context", default=None)
_request_context_var: ContextVar["RequestContext | None"] = ContextVar("request_context", default=None)


@dataclass
class UserContext:
    """
    Comprehensive user context for authorization throughout the request lifecycle.

    This class encapsulates all user-related information needed for authorization
    decisions and audit logging. It extends AuthenticatedUser with additional
    context like permissions, feature flags, and tenant information.

    Attributes:
        user: The authenticated user information from JWT
        permissions: Set of permission strings the user has
        roles: Set of roles assigned to the user
        tenant_id: Optional tenant/organization ID for multi-tenancy
        subscription_tier: User's subscription level (for feature gating)
        feature_flags: Dict of feature flags enabled for this user
        session_metadata: Additional session-specific metadata
        authenticated_at: Timestamp when the user was authenticated
    """

    user: AuthenticatedUser
    permissions: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    tenant_id: UUID | None = None
    subscription_tier: str = DEFAULT_SUBSCRIPTION_TIER
    feature_flags: dict[str, bool] = field(default_factory=dict)
    session_metadata: dict[str, Any] = field(default_factory=dict)
    authenticated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def user_id(self) -> UUID:
        """Get the user's ID."""
        return self.user.id

    @property
    def email(self) -> str | None:
        """Get the user's email."""
        return self.user.email

    @property
    def primary_role(self) -> str | None:
        """Get the user's primary role from the JWT."""
        return self.user.role

    def has_permission(self, permission: str) -> bool:
        """
        Check if the user has a specific permission.

        Args:
            permission: The permission string to check

        Returns:
            True if user has the permission, False otherwise
        """
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        """
        Check if the user has any of the specified permissions.

        Args:
            *permissions: Permission strings to check

        Returns:
            True if user has at least one permission, False otherwise
        """
        return bool(self.permissions.intersection(permissions))

    def has_all_permissions(self, *permissions: str) -> bool:
        """
        Check if the user has all of the specified permissions.

        Args:
            *permissions: Permission strings to check

        Returns:
            True if user has all permissions, False otherwise
        """
        return set(permissions).issubset(self.permissions)

    def has_role(self, role: str) -> bool:
        """
        Check if the user has a specific role.

        Args:
            role: The role string to check

        Returns:
            True if user has the role, False otherwise
        """
        return role in self.roles or self.primary_role == role

    def has_feature(self, feature: str) -> bool:
        """
        Check if a feature flag is enabled for the user.

        Args:
            feature: The feature flag name

        Returns:
            True if feature is enabled, False otherwise
        """
        return self.feature_flags.get(feature, False)

    def require_permission(self, permission: str) -> None:
        """
        Require a specific permission, raising AuthorizationError if not present.

        Args:
            permission: The required permission

        Raises:
            AuthorizationError: If user doesn't have the permission
        """
        if not self.has_permission(permission):
            logger.warning(
                "Permission denied",
                user_id=str(self.user_id),
                required_permission=permission,
                user_permissions=list(self.permissions),
            )
            raise AuthorizationError(f"Required permission '{permission}' not found")

    def require_role(self, role: str) -> None:
        """
        Require a specific role, raising AuthorizationError if not present.

        Args:
            role: The required role

        Raises:
            AuthorizationError: If user doesn't have the role
        """
        if not self.has_role(role):
            logger.warning(
                "Role denied",
                user_id=str(self.user_id),
                required_role=role,
                user_roles=list(self.roles),
            )
            raise AuthorizationError(f"Required role '{role}' not found")

    def to_log_context(self) -> dict[str, Any]:
        """
        Get a dictionary suitable for structured logging.

        Returns:
            Dictionary with user context for logging
        """
        return {
            "user_id": str(self.user_id),
            "email": self.email,
            "primary_role": self.primary_role,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "subscription_tier": self.subscription_tier,
        }

    @classmethod
    def from_authenticated_user(
        cls,
        user: AuthenticatedUser,
        permissions: set[str] | None = None,
        roles: set[str] | None = None,
        tenant_id: UUID | None = None,
    ) -> "UserContext":
        """
        Create UserContext from an AuthenticatedUser.

        This factory method builds UserContext by extracting additional
        information from the user's metadata.

        Args:
            user: The authenticated user from JWT validation
            permissions: Optional explicit permissions (otherwise derived from metadata)
            roles: Optional explicit roles (otherwise derived from metadata)
            tenant_id: Optional tenant ID (otherwise derived from metadata)

        Returns:
            Fully populated UserContext instance
        """
        # Extract permissions from app metadata if not provided
        if permissions is None:
            permissions = set(user.app_metadata.get(MetadataKeys.PERMISSIONS, []))

        # Extract roles from app metadata if not provided
        if roles is None:
            roles = set(user.app_metadata.get(MetadataKeys.ROLES, []))
            # Always include the JWT role
            if user.role:
                roles.add(user.role)

        # Extract tenant_id from app metadata if not provided
        if tenant_id is None:
            tenant_id_str = user.app_metadata.get(MetadataKeys.TENANT_ID)
            if tenant_id_str:
                try:
                    tenant_id = UUID(tenant_id_str)
                except (ValueError, TypeError):
                    pass

        # Extract subscription tier from user metadata
        subscription_tier = user.user_metadata.get(
            MetadataKeys.SUBSCRIPTION_TIER, DEFAULT_SUBSCRIPTION_TIER
        )

        # Extract feature flags from app metadata
        feature_flags = user.app_metadata.get(MetadataKeys.FEATURE_FLAGS, {})

        return cls(
            user=user,
            permissions=permissions,
            roles=roles,
            tenant_id=tenant_id,
            subscription_tier=subscription_tier,
            feature_flags=feature_flags,
            session_metadata={
                "email_confirmed": user.email_confirmed_at is not None,
                "created_at": user.created_at,
            },
        )


@dataclass
class RequestContext:
    """
    Complete request context combining user, request info, and database session.

    This class provides a unified context object that can be passed to services,
    enabling them to access everything they need without having to inject
    multiple dependencies.

    Attributes:
        user_context: The user context for the request (None if unauthenticated)
        request_id: Unique ID for request tracing
        db: Database session for the request
        path: The request URL path
        method: The HTTP method
        start_time: When the request started
        trace_id: Optional distributed trace ID
        metadata: Additional request metadata
    """

    request_id: str
    path: str
    method: str
    db: AsyncSession
    user_context: UserContext | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Check if the request has an authenticated user."""
        return self.user_context is not None

    @property
    def user_id(self) -> UUID | None:
        """Get the user ID if authenticated."""
        return self.user_context.user_id if self.user_context else None

    def require_authentication(self) -> UserContext:
        """
        Require authentication, returning the user context.

        Returns:
            The user context

        Raises:
            AuthorizationError: If not authenticated
        """
        if not self.user_context:
            raise AuthorizationError("Authentication required")
        return self.user_context

    def to_log_context(self) -> dict[str, Any]:
        """
        Get a dictionary suitable for structured logging.

        Returns:
            Dictionary with request context for logging
        """
        ctx = {
            "request_id": self.request_id,
            "path": self.path,
            "method": self.method,
            "trace_id": self.trace_id,
        }
        if self.user_context:
            ctx.update(self.user_context.to_log_context())
        return ctx


# Context variable accessors
def get_current_user_context() -> UserContext | None:
    """
    Get the current user context from the context variable.

    Returns:
        The current UserContext or None if not set
    """
    return _user_context_var.get()


def set_current_user_context(ctx: UserContext | None) -> None:
    """
    Set the current user context in the context variable.

    Args:
        ctx: The UserContext to set, or None to clear
    """
    _user_context_var.set(ctx)


def get_current_request_context() -> RequestContext | None:
    """
    Get the current request context from the context variable.

    Returns:
        The current RequestContext or None if not set
    """
    return _request_context_var.get()


def set_current_request_context(ctx: RequestContext | None) -> None:
    """
    Set the current request context in the context variable.

    Args:
        ctx: The RequestContext to set, or None to clear
    """
    _request_context_var.set(ctx)


def require_user_context() -> UserContext:
    """
    Get the current user context, raising if not present.

    Returns:
        The current UserContext

    Raises:
        AuthorizationError: If no user context is set
    """
    ctx = get_current_user_context()
    if ctx is None:
        raise AuthorizationError("User context required but not available")
    return ctx


def require_request_context() -> RequestContext:
    """
    Get the current request context, raising if not present.

    Returns:
        The current RequestContext

    Raises:
        RuntimeError: If no request context is set
    """
    ctx = get_current_request_context()
    if ctx is None:
        raise RuntimeError("Request context required but not available")
    return ctx
