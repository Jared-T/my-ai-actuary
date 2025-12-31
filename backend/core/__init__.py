"""Core module containing configuration, logging, and shared utilities."""

from core.config import settings
from core.database import (
    AsyncSessionLocal,
    Base,
    close_db,
    get_db,
    get_db_context,
    get_engine,
    get_session_factory,
    init_db,
)
from core.jwt_middleware import (
    DEFAULT_PUBLIC_PATH_PREFIXES,
    DEFAULT_PUBLIC_PATHS,
    JWTAuthMiddleware,
    StrictJWTAuthMiddleware,
    get_user_from_request,
    get_user_id_from_request,
)
from core.logging import configure_logging, get_logger

__all__ = [
    "settings",
    "configure_logging",
    "get_logger",
    "Base",
    "get_db",
    "get_db_context",
    "get_engine",
    "get_session_factory",
    "AsyncSessionLocal",  # Backward compatibility alias
    "init_db",
    "close_db",
    # JWT Middleware exports
    "JWTAuthMiddleware",
    "StrictJWTAuthMiddleware",
    "get_user_from_request",
    "get_user_id_from_request",
    "DEFAULT_PUBLIC_PATHS",
    "DEFAULT_PUBLIC_PATH_PREFIXES",
]
