"""
Alembic migration environment configuration.

Configures Alembic to use our SQLAlchemy models and database settings.
Supports both online (connected) and offline (SQL generation) migrations.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import our models to register them with SQLAlchemy
from core.config import settings
from core.database import Base

# Import all models to ensure they're registered
from models import (  # noqa: F401
    Approval,
    Artefact,
    AuditLog,
    ChatMessage,
    Engagement,
    Session,
    WorkflowRun,
)

# Alembic Config object for access to .ini file values
config = context.config

# Set the SQLAlchemy URL from our settings
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

# Set up loggers from config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    Useful for reviewing migrations before applying them.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations asynchronously for async engine support.
    """
    # Use async-compatible URL for the engine
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Connects to the database and applies migrations directly.
    Uses async connection for compatibility with asyncpg.
    """
    asyncio.run(run_async_migrations())


# Determine execution mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
