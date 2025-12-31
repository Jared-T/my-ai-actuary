"""
API v1 Domain Routers.

This module exports all domain-specific routers for API v1.
Each router handles a specific domain of functionality.

Domains:
- chat: Agent conversations and session management
- workflows: Workflow definitions and execution
- knowledge: Knowledge base and actuarial methods
- observability: Metrics, tracing, and audit trails
- system: Backup, recovery, and administrative tasks
"""

from api.v1.routers import chat, knowledge, observability, system, workflows

__all__ = [
    "chat",
    "knowledge",
    "observability",
    "system",
    "workflows",
]
