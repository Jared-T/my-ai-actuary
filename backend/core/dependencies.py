"""
FastAPI dependencies for the dependency injection system.

This module provides FastAPI-compatible dependencies that integrate the
UserContext, RequestContext, and ServiceContainer with the request lifecycle.

Usage in routes:
    from core.dependencies import (
        UserContextDep,
        ServiceContainerDep,
        RequirePermission,
    )

    @router.get("/protected")
    async def protected_endpoint(
        user_ctx: UserContextDep,
        container: ServiceContainerDep,
    ):
        service = container.get_agent_service()
        return await service.do_something(user_ctx.user_id)
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import AuthenticatedUser, get_current_user, get_optional_user
from core.container import ServiceContainer, create_container
from core.context import (
    RequestContext,
    UserContext,
    set_current_request_context,
    set_current_user_context,
)
from core.database import get_db
from core.exceptions import AuthorizationError
from core.logging import get_logger

logger = get_logger(__name__)


async def get_user_context(
    user: AuthenticatedUser = Depends(get_current_user),
) -> UserContext:
    """
    FastAPI dependency to get a fully populated UserContext.

    This dependency requires authentication and builds a comprehensive
    UserContext from the authenticated user's information.

    Args:
        user: The authenticated user from JWT validation

    Returns:
        Fully populated UserContext
    """
    ctx = UserContext.from_authenticated_user(user)

    # Store in context variable for access in nested code
    set_current_user_context(ctx)

    logger.debug(
        "Created UserContext",
        user_id=str(ctx.user_id),
        roles=list(ctx.roles),
        permissions_count=len(ctx.permissions),
    )

    return ctx


async def get_optional_user_context(
    user: AuthenticatedUser | None = Depends(get_optional_user),
) -> UserContext | None:
    """
    FastAPI dependency to get UserContext for optionally authenticated endpoints.

    Returns None if no authentication is provided, or a full UserContext
    if authentication is present.

    Args:
        user: The authenticated user (optional)

    Returns:
        UserContext if authenticated, None otherwise
    """
    if user is None:
        set_current_user_context(None)
        return None

    ctx = UserContext.from_authenticated_user(user)
    set_current_user_context(ctx)

    logger.debug(
        "Created optional UserContext",
        user_id=str(ctx.user_id),
    )

    return ctx


async def get_request_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext | None = Depends(get_optional_user_context),
) -> RequestContext:
    """
    FastAPI dependency to get a complete RequestContext.

    This combines user context, request information, and database session
    into a unified context object.

    Args:
        request: The FastAPI request
        db: Database session
        user_context: Optional user context

    Returns:
        Complete RequestContext
    """
    ctx = RequestContext(
        request_id=getattr(request.state, "request_id", "unknown"),
        path=str(request.url.path),
        method=request.method,
        db=db,
        user_context=user_context,
        trace_id=getattr(request.state, "trace_id", None),
    )

    # Store in context variable
    set_current_request_context(ctx)

    return ctx


async def get_service_container(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext | None = Depends(get_optional_user_context),
) -> ServiceContainer:
    """
    FastAPI dependency to get a ServiceContainer for the request.

    The container provides access to all services with consistent
    user context propagation.

    Args:
        request: The FastAPI request
        db: Database session
        user_context: Optional user context

    Returns:
        Configured ServiceContainer
    """
    request_id = getattr(request.state, "request_id", None)
    return create_container(
        db=db,
        user_context=user_context,
        request_id=request_id,
    )


async def get_authenticated_container(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_context: UserContext = Depends(get_user_context),
) -> ServiceContainer:
    """
    FastAPI dependency to get a ServiceContainer that requires authentication.

    This is a convenience dependency that ensures authentication and provides
    a container in one step.

    Args:
        request: The FastAPI request
        db: Database session
        user_context: The authenticated user context (required)

    Returns:
        Configured ServiceContainer with authenticated user
    """
    request_id = getattr(request.state, "request_id", None)
    return create_container(
        db=db,
        user_context=user_context,
        request_id=request_id,
    )


def require_permission(permission: str) -> Callable[..., Awaitable[UserContext]]:
    """
    Factory function to create a dependency that requires a specific permission.

    Usage:
        @router.get("/admin/users")
        async def list_users(
            user_ctx: UserContext = Depends(require_permission("users:read")),
        ):
            ...

    Args:
        permission: The required permission string

    Returns:
        A FastAPI dependency function
    """

    async def permission_checker(
        user_context: UserContext = Depends(get_user_context),
    ) -> UserContext:
        if not user_context.has_permission(permission):
            logger.warning(
                "Permission check failed",
                user_id=str(user_context.user_id),
                required_permission=permission,
                user_permissions=list(user_context.permissions),
            )
            raise AuthorizationError(f"Required permission '{permission}' not found")
        return user_context

    return permission_checker


def require_any_permission(*permissions: str) -> Callable[..., Awaitable[UserContext]]:
    """
    Factory function to create a dependency that requires any of the permissions.

    Args:
        *permissions: The permission strings (user needs at least one)

    Returns:
        A FastAPI dependency function
    """

    async def permission_checker(
        user_context: UserContext = Depends(get_user_context),
    ) -> UserContext:
        if not user_context.has_any_permission(*permissions):
            logger.warning(
                "Permission check failed (any)",
                user_id=str(user_context.user_id),
                required_permissions=list(permissions),
                user_permissions=list(user_context.permissions),
            )
            raise AuthorizationError(
                f"Required one of permissions {permissions}, but none found"
            )
        return user_context

    return permission_checker


def require_all_permissions(*permissions: str) -> Callable[..., Awaitable[UserContext]]:
    """
    Factory function to create a dependency that requires all specified permissions.

    Args:
        *permissions: The permission strings (user needs all)

    Returns:
        A FastAPI dependency function
    """

    async def permission_checker(
        user_context: UserContext = Depends(get_user_context),
    ) -> UserContext:
        if not user_context.has_all_permissions(*permissions):
            missing = set(permissions) - user_context.permissions
            logger.warning(
                "Permission check failed (all)",
                user_id=str(user_context.user_id),
                required_permissions=list(permissions),
                missing_permissions=list(missing),
            )
            raise AuthorizationError(
                f"Missing required permissions: {missing}"
            )
        return user_context

    return permission_checker


def require_role(role: str) -> Callable[..., Awaitable[UserContext]]:
    """
    Factory function to create a dependency that requires a specific role.

    Usage:
        @router.get("/admin/dashboard")
        async def admin_dashboard(
            user_ctx: UserContext = Depends(require_role("admin")),
        ):
            ...

    Args:
        role: The required role string

    Returns:
        A FastAPI dependency function
    """

    async def role_checker(
        user_context: UserContext = Depends(get_user_context),
    ) -> UserContext:
        if not user_context.has_role(role):
            logger.warning(
                "Role check failed",
                user_id=str(user_context.user_id),
                required_role=role,
                user_roles=list(user_context.roles),
            )
            raise AuthorizationError(f"Required role '{role}' not found")
        return user_context

    return role_checker


def require_feature(feature: str) -> Callable[..., Awaitable[UserContext]]:
    """
    Factory function to create a dependency that requires a feature flag.

    Usage:
        @router.get("/beta/new-feature")
        async def new_feature(
            user_ctx: UserContext = Depends(require_feature("beta_features")),
        ):
            ...

    Args:
        feature: The required feature flag name

    Returns:
        A FastAPI dependency function
    """

    async def feature_checker(
        user_context: UserContext = Depends(get_user_context),
    ) -> UserContext:
        if not user_context.has_feature(feature):
            logger.warning(
                "Feature check failed",
                user_id=str(user_context.user_id),
                required_feature=feature,
            )
            raise AuthorizationError(f"Feature '{feature}' not enabled for this user")
        return user_context

    return feature_checker


# Type aliases for cleaner endpoint signatures
UserContextDep = Annotated[UserContext, Depends(get_user_context)]
OptionalUserContextDep = Annotated[UserContext | None, Depends(get_optional_user_context)]
RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]
ServiceContainerDep = Annotated[ServiceContainer, Depends(get_service_container)]
AuthenticatedContainerDep = Annotated[ServiceContainer, Depends(get_authenticated_container)]
