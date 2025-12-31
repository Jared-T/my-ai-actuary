"""
System Domain Router - API v1.

Aggregates all system administration endpoints including:
- Backup and recovery operations
- CLI task management (Codex CLI integration)
- System configuration (future)

This domain handles system-level operations and administration.
"""

from fastapi import APIRouter

# Import existing route modules
from api.routes import backup, cli_tasks

# Create the system domain router
router = APIRouter(tags=["System"])

# Include backup routes
router.include_router(
    backup.router,
    prefix="",
    tags=["Backup"],
)

# Include recovery routes
router.include_router(
    backup.recovery_router,
    prefix="",
    tags=["Recovery"],
)

# Include CLI task routes
router.include_router(
    cli_tasks.router,
    prefix="",
    tags=["CLI Tasks"],
)

# Include CLI batch task routes
router.include_router(
    cli_tasks.batch_router,
    prefix="",
    tags=["CLI Batch Tasks"],
)
