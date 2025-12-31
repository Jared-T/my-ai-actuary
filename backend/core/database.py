"""
Database connection and session management using SQLAlchemy async.

Provides async database engine, session factory, and dependency injection
for FastAPI endpoints. Uses connection pooling for production readiness.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


# Naming convention for constraints (required for Alembic auto-migrations)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base class.

    All models inherit from this class. Provides consistent naming
    conventions for database constraints.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Module-level state for lazy initialization
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _create_engine() -> AsyncEngine:
    """
    Create async database engine with connection pooling.

    Returns:
        AsyncEngine configured for the application.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_pool_overflow,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour
    )

    # Log connection events in debug mode
    if settings.debug:

        @event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_connection: Any, connection_record: Any) -> None:
            logger.debug("Database connection established", connection=str(connection_record))

    return engine


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine (lazy initialization).

    Returns:
        The global AsyncEngine instance.
    """
    global _engine
    if _engine is None:
        _engine = _create_engine()
        logger.info("Database engine initialized", database_url=settings.database_url[:50] + "...")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory (lazy initialization).

    Returns:
        The global session factory instance.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# Backward compatibility alias - use get_session_factory() instead
AsyncSessionLocal = get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Yields an async session and ensures proper cleanup on request completion.
    Use with FastAPI's Depends() for automatic injection.

    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI requests.

    Useful for background tasks, scripts, and testing.

    Example:
        async with get_db_context() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in the models. Should be used only for
    development/testing. Production should use Alembic migrations.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")


async def close_db() -> None:
    """
    Close database connections.

    Should be called during application shutdown to clean up resources.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connections closed")
