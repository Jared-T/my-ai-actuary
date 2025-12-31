"""
API Version 1 Routes.

This module provides the versioned API router that aggregates all domain-specific
routes under the /api/v1 prefix.

Domain Organization:
- chat: Agent conversations, sessions, and chat-related endpoints
- projects: Project management and engagement-related endpoints
- workflows: Workflow definitions, validation, and execution
- knowledge: Knowledge base, methods, templates, and precedents
- observability: Metrics, tracing, audit trails, and health checks
- system: Backup, recovery, CLI tasks, and system administration
"""

from fastapi import APIRouter

from api.v1.routers import (
    chat,
    knowledge,
    observability,
    system,
    workflows,
)

# Create the main v1 router
router = APIRouter(prefix="/api/v1")

# Include domain routers
router.include_router(chat.router)
router.include_router(workflows.router)
router.include_router(knowledge.router)
router.include_router(observability.router)
router.include_router(system.router)

__all__ = ["router"]
