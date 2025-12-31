"""
Role-Based Access Control (RBAC) system for the AI Actuary application.

Provides:
- Role and permission definitions
- Permission checking utilities
- FastAPI dependencies for role/permission-based authorization
"""

from enum import Enum
from typing import Annotated, Callable, Any
from uuid import UUID

from fastapi import Depends

from core.auth import AuthenticatedUser, get_current_user
from core.exceptions import AuthorizationError
from core.logging import get_logger

logger = get_logger(__name__)


class Role(str, Enum):
    """
    Application roles with hierarchical permissions.

    Role Hierarchy:
    - ADMIN: Full system access, can manage users and all resources
    - MANAGER: Can manage engagements, projects, and team members
    - ANALYST: Can create and edit work products, run analyses
    - REVIEWER: Read-only access with ability to approve/reject work
    """
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    REVIEWER = "reviewer"


class Permission(str, Enum):
    """
    Granular permissions that can be assigned to roles.

    Permissions are organized by domain:
    - User management (users:*)
    - Engagement management (engagements:*)
    - Project management (projects:*)
    - Workflow execution (workflows:*)
    - Artefact management (artefacts:*)
    - Approval workflows (approvals:*)
    - System administration (system:*)
    - Knowledge base (knowledge:*)
    """
    # User management
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_MANAGE_ROLES = "users:manage_roles"

    # Engagement management
    ENGAGEMENTS_READ = "engagements:read"
    ENGAGEMENTS_CREATE = "engagements:create"
    ENGAGEMENTS_UPDATE = "engagements:update"
    ENGAGEMENTS_DELETE = "engagements:delete"
    ENGAGEMENTS_ASSIGN = "engagements:assign"

    # Project management
    PROJECTS_READ = "projects:read"
    PROJECTS_CREATE = "projects:create"
    PROJECTS_UPDATE = "projects:update"
    PROJECTS_DELETE = "projects:delete"
    PROJECTS_ASSIGN = "projects:assign"

    # Workflow execution
    WORKFLOWS_READ = "workflows:read"
    WORKFLOWS_EXECUTE = "workflows:execute"
    WORKFLOWS_CANCEL = "workflows:cancel"

    # Artefact management
    ARTEFACTS_READ = "artefacts:read"
    ARTEFACTS_CREATE = "artefacts:create"
    ARTEFACTS_UPDATE = "artefacts:update"
    ARTEFACTS_DELETE = "artefacts:delete"
    ARTEFACTS_DOWNLOAD = "artefacts:download"

    # Approval workflows
    APPROVALS_READ = "approvals:read"
    APPROVALS_CREATE = "approvals:create"
    APPROVALS_APPROVE = "approvals:approve"
    APPROVALS_REJECT = "approvals:reject"

    # Knowledge base
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_CREATE = "knowledge:create"
    KNOWLEDGE_UPDATE = "knowledge:update"
    KNOWLEDGE_DELETE = "knowledge:delete"

    # System administration
    SYSTEM_SETTINGS = "system:settings"
    SYSTEM_AUDIT = "system:audit"
    SYSTEM_BACKUPS = "system:backups"
    SYSTEM_METRICS = "system:metrics"

    # Session management
    SESSIONS_READ = "sessions:read"
    SESSIONS_CREATE = "sessions:create"
    SESSIONS_DELETE = "sessions:delete"


# Role to permissions mapping
# Each role inherits all permissions from roles below it in the hierarchy
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.REVIEWER: {
        # Read-only access plus approval capabilities
        Permission.ENGAGEMENTS_READ,
        Permission.PROJECTS_READ,
        Permission.WORKFLOWS_READ,
        Permission.ARTEFACTS_READ,
        Permission.ARTEFACTS_DOWNLOAD,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_APPROVE,
        Permission.APPROVALS_REJECT,
        Permission.KNOWLEDGE_READ,
        Permission.SESSIONS_READ,
    },
    Role.ANALYST: {
        # Reviewer permissions plus creation/editing
        Permission.ENGAGEMENTS_READ,
        Permission.PROJECTS_READ,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_UPDATE,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_EXECUTE,
        Permission.ARTEFACTS_READ,
        Permission.ARTEFACTS_CREATE,
        Permission.ARTEFACTS_UPDATE,
        Permission.ARTEFACTS_DOWNLOAD,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_CREATE,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_CREATE,
        Permission.SESSIONS_READ,
        Permission.SESSIONS_CREATE,
    },
    Role.MANAGER: {
        # Analyst permissions plus management capabilities
        Permission.USERS_READ,
        Permission.ENGAGEMENTS_READ,
        Permission.ENGAGEMENTS_CREATE,
        Permission.ENGAGEMENTS_UPDATE,
        Permission.ENGAGEMENTS_ASSIGN,
        Permission.PROJECTS_READ,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_UPDATE,
        Permission.PROJECTS_DELETE,
        Permission.PROJECTS_ASSIGN,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_EXECUTE,
        Permission.WORKFLOWS_CANCEL,
        Permission.ARTEFACTS_READ,
        Permission.ARTEFACTS_CREATE,
        Permission.ARTEFACTS_UPDATE,
        Permission.ARTEFACTS_DELETE,
        Permission.ARTEFACTS_DOWNLOAD,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_CREATE,
        Permission.APPROVALS_APPROVE,
        Permission.APPROVALS_REJECT,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_CREATE,
        Permission.KNOWLEDGE_UPDATE,
        Permission.SESSIONS_READ,
        Permission.SESSIONS_CREATE,
        Permission.SESSIONS_DELETE,
        Permission.SYSTEM_METRICS,
    },
    Role.ADMIN: {
        # All permissions
        Permission.USERS_READ,
        Permission.USERS_CREATE,
        Permission.USERS_UPDATE,
        Permission.USERS_DELETE,
        Permission.USERS_MANAGE_ROLES,
        Permission.ENGAGEMENTS_READ,
        Permission.ENGAGEMENTS_CREATE,
        Permission.ENGAGEMENTS_UPDATE,
        Permission.ENGAGEMENTS_DELETE,
        Permission.ENGAGEMENTS_ASSIGN,
        Permission.PROJECTS_READ,
        Permission.PROJECTS_CREATE,
        Permission.PROJECTS_UPDATE,
        Permission.PROJECTS_DELETE,
        Permission.PROJECTS_ASSIGN,
        Permission.WORKFLOWS_READ,
        Permission.WORKFLOWS_EXECUTE,
        Permission.WORKFLOWS_CANCEL,
        Permission.ARTEFACTS_READ,
        Permission.ARTEFACTS_CREATE,
        Permission.ARTEFACTS_UPDATE,
        Permission.ARTEFACTS_DELETE,
        Permission.ARTEFACTS_DOWNLOAD,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_CREATE,
        Permission.APPROVALS_APPROVE,
        Permission.APPROVALS_REJECT,
        Permission.KNOWLEDGE_READ,
        Permission.KNOWLEDGE_CREATE,
        Permission.KNOWLEDGE_UPDATE,
        Permission.KNOWLEDGE_DELETE,
        Permission.SYSTEM_SETTINGS,
        Permission.SYSTEM_AUDIT,
        Permission.SYSTEM_BACKUPS,
        Permission.SYSTEM_METRICS,
        Permission.SESSIONS_READ,
        Permission.SESSIONS_CREATE,
        Permission.SESSIONS_DELETE,
    },
}


def get_role_permissions(role: Role) -> set[Permission]:
    """
    Get all permissions for a given role.

    Args:
        role: The role to get permissions for

    Returns:
        Set of permissions granted to the role
    """
    return ROLE_PERMISSIONS.get(role, set())


def role_has_permission(role: Role, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: The role to check
        permission: The permission to check for

    Returns:
        True if the role has the permission, False otherwise
    """
    return permission in get_role_permissions(role)


def get_user_role(user: AuthenticatedUser) -> Role | None:
    """
    Extract the application role from an authenticated user.

    The role is stored in the user's app_metadata under the 'app_role' key.
    Falls back to 'role' key for backward compatibility.

    Args:
        user: The authenticated user

    Returns:
        The user's Role, or None if no valid role is assigned
    """
    # Check app_metadata first (preferred location)
    app_role = user.get_app_metadata("app_role")
    if app_role:
        try:
            return Role(app_role)
        except ValueError:
            logger.warning(
                "Invalid app_role in app_metadata",
                user_id=str(user.id),
                app_role=app_role,
            )

    # Fall back to user_metadata
    user_role = user.get_metadata("app_role")
    if user_role:
        try:
            return Role(user_role)
        except ValueError:
            logger.warning(
                "Invalid app_role in user_metadata",
                user_id=str(user.id),
                app_role=user_role,
            )

    return None


def get_user_permissions(user: AuthenticatedUser) -> set[Permission]:
    """
    Get all permissions for an authenticated user based on their role.

    Args:
        user: The authenticated user

    Returns:
        Set of permissions granted to the user
    """
    role = get_user_role(user)
    if role is None:
        return set()
    return get_role_permissions(role)


def user_has_permission(user: AuthenticatedUser, permission: Permission) -> bool:
    """
    Check if a user has a specific permission.

    Args:
        user: The authenticated user
        permission: The permission to check for

    Returns:
        True if the user has the permission, False otherwise
    """
    return permission in get_user_permissions(user)


def user_has_any_permission(user: AuthenticatedUser, permissions: list[Permission]) -> bool:
    """
    Check if a user has any of the specified permissions.

    Args:
        user: The authenticated user
        permissions: List of permissions to check

    Returns:
        True if the user has at least one of the permissions
    """
    user_perms = get_user_permissions(user)
    return bool(user_perms & set(permissions))


def user_has_all_permissions(user: AuthenticatedUser, permissions: list[Permission]) -> bool:
    """
    Check if a user has all of the specified permissions.

    Args:
        user: The authenticated user
        permissions: List of permissions to check

    Returns:
        True if the user has all of the permissions
    """
    user_perms = get_user_permissions(user)
    return set(permissions).issubset(user_perms)


def user_has_role(user: AuthenticatedUser, role: Role) -> bool:
    """
    Check if a user has a specific role.

    Args:
        user: The authenticated user
        role: The role to check for

    Returns:
        True if the user has the role, False otherwise
    """
    return get_user_role(user) == role


def user_has_any_role(user: AuthenticatedUser, roles: list[Role]) -> bool:
    """
    Check if a user has any of the specified roles.

    Args:
        user: The authenticated user
        roles: List of roles to check

    Returns:
        True if the user has at least one of the roles
    """
    user_role = get_user_role(user)
    return user_role in roles


# FastAPI Dependencies for RBAC


def require_permission(permission: Permission) -> Callable:
    """
    FastAPI dependency factory that requires a specific permission.

    Usage:
        @router.get("/engagements")
        async def list_engagements(
            user: AuthenticatedUser = Depends(require_permission(Permission.ENGAGEMENTS_READ)),
        ):
            ...

    Args:
        permission: The permission required to access the endpoint

    Returns:
        A FastAPI dependency function
    """
    async def permission_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user_has_permission(user, permission):
            logger.warning(
                "Permission denied",
                user_id=str(user.id),
                required_permission=permission.value,
                user_role=get_user_role(user),
            )
            raise AuthorizationError(
                f"Permission '{permission.value}' required"
            )
        return user

    return permission_checker


def require_any_permission(permissions: list[Permission]) -> Callable:
    """
    FastAPI dependency factory that requires any of the specified permissions.

    Usage:
        @router.get("/reports")
        async def view_reports(
            user: AuthenticatedUser = Depends(
                require_any_permission([Permission.ARTEFACTS_READ, Permission.SYSTEM_AUDIT])
            ),
        ):
            ...

    Args:
        permissions: List of permissions, at least one of which is required

    Returns:
        A FastAPI dependency function
    """
    async def permission_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user_has_any_permission(user, permissions):
            logger.warning(
                "Permission denied - none of required permissions",
                user_id=str(user.id),
                required_permissions=[p.value for p in permissions],
                user_role=get_user_role(user),
            )
            raise AuthorizationError(
                f"One of permissions required: {', '.join(p.value for p in permissions)}"
            )
        return user

    return permission_checker


def require_all_permissions(permissions: list[Permission]) -> Callable:
    """
    FastAPI dependency factory that requires all of the specified permissions.

    Usage:
        @router.delete("/engagements/{id}")
        async def delete_engagement(
            id: UUID,
            user: AuthenticatedUser = Depends(
                require_all_permissions([Permission.ENGAGEMENTS_DELETE, Permission.SYSTEM_AUDIT])
            ),
        ):
            ...

    Args:
        permissions: List of permissions, all of which are required

    Returns:
        A FastAPI dependency function
    """
    async def permission_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user_has_all_permissions(user, permissions):
            missing = set(permissions) - get_user_permissions(user)
            logger.warning(
                "Permission denied - missing required permissions",
                user_id=str(user.id),
                required_permissions=[p.value for p in permissions],
                missing_permissions=[p.value for p in missing],
                user_role=get_user_role(user),
            )
            raise AuthorizationError(
                f"All permissions required: {', '.join(p.value for p in permissions)}"
            )
        return user

    return permission_checker


def require_app_role(role: Role) -> Callable:
    """
    FastAPI dependency factory that requires a specific application role.

    Usage:
        @router.get("/admin/dashboard")
        async def admin_dashboard(
            user: AuthenticatedUser = Depends(require_app_role(Role.ADMIN)),
        ):
            ...

    Args:
        role: The role required to access the endpoint

    Returns:
        A FastAPI dependency function
    """
    async def role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user_has_role(user, role):
            logger.warning(
                "Role denied",
                user_id=str(user.id),
                required_role=role.value,
                user_role=get_user_role(user),
            )
            raise AuthorizationError(
                f"Role '{role.value}' required"
            )
        return user

    return role_checker


def require_any_app_role(roles: list[Role]) -> Callable:
    """
    FastAPI dependency factory that requires any of the specified roles.

    Usage:
        @router.get("/management/dashboard")
        async def management_dashboard(
            user: AuthenticatedUser = Depends(
                require_any_app_role([Role.ADMIN, Role.MANAGER])
            ),
        ):
            ...

    Args:
        roles: List of roles, at least one of which is required

    Returns:
        A FastAPI dependency function
    """
    async def role_checker(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if not user_has_any_role(user, roles):
            logger.warning(
                "Role denied - none of required roles",
                user_id=str(user.id),
                required_roles=[r.value for r in roles],
                user_role=get_user_role(user),
            )
            raise AuthorizationError(
                f"One of roles required: {', '.join(r.value for r in roles)}"
            )
        return user

    return role_checker


# Type aliases for cleaner endpoint signatures
AdminUser = Annotated[AuthenticatedUser, Depends(require_app_role(Role.ADMIN))]
ManagerUser = Annotated[AuthenticatedUser, Depends(require_any_app_role([Role.ADMIN, Role.MANAGER]))]
AnalystUser = Annotated[AuthenticatedUser, Depends(require_any_app_role([Role.ADMIN, Role.MANAGER, Role.ANALYST]))]
ReviewerUser = Annotated[AuthenticatedUser, Depends(require_any_app_role([Role.ADMIN, Role.MANAGER, Role.ANALYST, Role.REVIEWER]))]
