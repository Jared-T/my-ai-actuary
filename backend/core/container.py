"""
Service container for dependency injection.

Provides a centralized container for managing service instances with
request-scoped lifecycle. This enables clean dependency injection where
services have access to user context throughout the request.

Key features:
- Request-scoped service instances (created once per request)
- Lazy service initialization
- User context propagation to all services
- Type-safe service access
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import UserContext

if TYPE_CHECKING:
    from services.agent_service import AgentService
    from services.audit_service import AuditService
    from services.backup_service import BackupService
    from services.cli_task_service import CLITaskService
    from services.embedding_service import EmbeddingService
    from services.knowledge_base_service import KnowledgeBaseService
    from services.recovery_service import RecoveryService

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class ServiceRegistry:
    """
    Registry for service factories.

    This class maintains a mapping of service types to their factory functions,
    enabling the container to create services on-demand.
    """

    _factories: dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, factory: Any) -> None:
        """
        Register a service factory.

        Args:
            name: The service name (used as key)
            factory: A callable that creates the service instance
        """
        cls._factories[name] = factory
        logger.debug("Registered service factory", service_name=name)

    @classmethod
    def get_factory(cls, name: str) -> Any | None:
        """
        Get a registered factory by name.

        Args:
            name: The service name

        Returns:
            The factory callable, or None if not registered
        """
        return cls._factories.get(name)

    @classmethod
    def list_services(cls) -> list[str]:
        """
        List all registered service names.

        Returns:
            List of registered service names
        """
        return list(cls._factories.keys())


@dataclass
class ServiceContainer:
    """
    Request-scoped service container.

    This container holds references to services for a single request,
    ensuring consistent context across all service calls. Services are
    lazily initialized on first access.

    Usage:
        container = ServiceContainer(db=session, user_context=user_ctx)
        agent_service = container.get_agent_service()
        await agent_service.run_agent(...)

    Attributes:
        db: The database session for this request
        user_context: The user context (None for unauthenticated requests)
        request_id: Unique request identifier for tracing
        _services: Cache of instantiated services
    """

    db: AsyncSession
    user_context: UserContext | None = None
    request_id: str | None = None
    _services: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_authenticated(self) -> bool:
        """Check if there's an authenticated user."""
        return self.user_context is not None

    @property
    def user_id(self) -> UUID | None:
        """Get the current user's ID, if authenticated."""
        return self.user_context.user_id if self.user_context else None

    def require_auth(self) -> UserContext:
        """
        Require authentication, returning the user context.

        Returns:
            The user context

        Raises:
            AuthorizationError: If not authenticated
        """
        from core.exceptions import AuthorizationError

        if not self.user_context:
            raise AuthorizationError("Authentication required")
        return self.user_context

    def _create_service(self, service_class: type[T], **kwargs: Any) -> T:
        """
        Create a service instance with standard dependencies.

        Args:
            service_class: The service class to instantiate
            **kwargs: Additional keyword arguments for the service

        Returns:
            Configured service instance
        """
        return service_class(db=self.db, **kwargs)

    def get_agent_service(self) -> "AgentService":
        """
        Get or create the AgentService.

        Returns:
            AgentService instance configured with current context
        """
        if "agent" not in self._services:
            from services.agent_service import AgentService

            self._services["agent"] = AgentService(db=self.db)
            logger.debug(
                "Created AgentService",
                request_id=self.request_id,
                user_id=str(self.user_id) if self.user_id else None,
            )
        return self._services["agent"]

    def get_backup_service(self) -> "BackupService":
        """
        Get or create the BackupService.

        Returns:
            BackupService instance configured with current context
        """
        if "backup" not in self._services:
            from services.backup_service import BackupService

            self._services["backup"] = BackupService(db=self.db)
            logger.debug(
                "Created BackupService",
                request_id=self.request_id,
            )
        return self._services["backup"]

    def get_recovery_service(self) -> "RecoveryService":
        """
        Get or create the RecoveryService.

        Returns:
            RecoveryService instance configured with current context
        """
        if "recovery" not in self._services:
            from services.recovery_service import RecoveryService

            self._services["recovery"] = RecoveryService(db=self.db)
            logger.debug(
                "Created RecoveryService",
                request_id=self.request_id,
            )
        return self._services["recovery"]

    def get_cli_task_service(self) -> "CLITaskService":
        """
        Get or create the CLITaskService.

        Returns:
            CLITaskService instance configured with current context
        """
        if "cli_task" not in self._services:
            from services.cli_task_service import CLITaskService

            self._services["cli_task"] = CLITaskService(db=self.db)
            logger.debug(
                "Created CLITaskService",
                request_id=self.request_id,
            )
        return self._services["cli_task"]

    def get_knowledge_base_service(self) -> "KnowledgeBaseService":
        """
        Get or create the KnowledgeBaseService.

        Returns:
            KnowledgeBaseService instance configured with current context
        """
        if "knowledge_base" not in self._services:
            from services.knowledge_base_service import KnowledgeBaseService

            self._services["knowledge_base"] = KnowledgeBaseService(db=self.db)
            logger.debug(
                "Created KnowledgeBaseService",
                request_id=self.request_id,
            )
        return self._services["knowledge_base"]

    def get_audit_service(self) -> "AuditService":
        """
        Get or create the AuditService.

        Returns:
            AuditService instance configured with current context
        """
        if "audit" not in self._services:
            from services.audit_service import AuditService

            self._services["audit"] = AuditService(db=self.db)
            logger.debug(
                "Created AuditService",
                request_id=self.request_id,
            )
        return self._services["audit"]

    def get_embedding_service(self) -> "EmbeddingService":
        """
        Get or create the EmbeddingService.

        Returns:
            EmbeddingService instance (singleton, no db required)
        """
        if "embedding" not in self._services:
            from services.embedding_service import EmbeddingService

            self._services["embedding"] = EmbeddingService()
            logger.debug(
                "Created EmbeddingService",
                request_id=self.request_id,
            )
        return self._services["embedding"]


def create_container(
    db: AsyncSession,
    user_context: UserContext | None = None,
    request_id: str | None = None,
) -> ServiceContainer:
    """
    Factory function to create a ServiceContainer.

    This is the preferred way to create containers, as it allows
    for future enhancements without changing client code.

    Args:
        db: Database session for the request
        user_context: User context if authenticated
        request_id: Request ID for tracing

    Returns:
        Configured ServiceContainer instance
    """
    container = ServiceContainer(
        db=db,
        user_context=user_context,
        request_id=request_id,
    )

    logger.debug(
        "Created ServiceContainer",
        request_id=request_id,
        authenticated=user_context is not None,
        user_id=str(user_context.user_id) if user_context else None,
    )

    return container
