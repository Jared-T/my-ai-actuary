"""
Observability Domain Router - API v1.

Aggregates all observability-related endpoints including:
- Distributed tracing
- Metrics and performance monitoring
- Comprehensive audit trail system
- Health checks (only for v1 namespace)

This domain handles monitoring, debugging, and compliance.
"""

from fastapi import APIRouter

# Import existing route modules
from api.routes import audit_trail, metrics, tracing

# Create the observability domain router
router = APIRouter(tags=["Observability"])

# Include tracing routes
router.include_router(
    tracing.router,
    prefix="",
    tags=["Tracing"],
)

# Include metrics routes
router.include_router(
    metrics.router,
    prefix="",
    tags=["Metrics"],
)

# Include audit trail routes
router.include_router(
    audit_trail.router,
    prefix="",
    tags=["Audit Trail"],
)
