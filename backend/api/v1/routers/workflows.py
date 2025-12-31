"""
Workflows Domain Router - API v1.

Aggregates all workflow-related endpoints including:
- Workflow definition management (CRUD)
- Workflow validation (JSON, YAML)
- Workflow types, step types, and data types
- Workflow export and execution order

This domain handles actuarial workflow automation.
"""

from fastapi import APIRouter

# Import existing route modules
from api.routes import workflows

# Create the workflows domain router
router = APIRouter(tags=["Workflows"])

# Include workflow definition routes
router.include_router(
    workflows.router,
    prefix="",
    tags=["Workflow Definitions"],
)
