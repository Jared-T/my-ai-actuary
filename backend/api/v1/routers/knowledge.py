"""
Knowledge Domain Router - API v1.

Aggregates all knowledge base-related endpoints including:
- Actuarial methods library
- Document templates
- Precedent cases
- Knowledge search and retrieval

This domain handles the actuarial knowledge repository.
"""

from fastapi import APIRouter

# Import existing route modules
from api.routes import knowledge_base

# Create the knowledge domain router
router = APIRouter(tags=["Knowledge Base"])

# Include knowledge base routes
router.include_router(
    knowledge_base.router,
    prefix="",
    tags=["Actuarial Knowledge"],
)
