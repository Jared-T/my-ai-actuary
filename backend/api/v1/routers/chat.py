"""
Chat Domain Router - API v1.

Aggregates all chat-related endpoints including:
- Agent conversations and execution
- Session management
- Conversation history and statistics
- Orchestration and intelligent routing

This domain handles all user-facing chat interactions with AI agents.
"""

from fastapi import APIRouter

# Import existing route modules
from api.routes import agents, conversations, orchestration

# Create the chat domain router
router = APIRouter(tags=["Chat"])

# Include agent routes (conversations, session management)
router.include_router(
    agents.router,
    prefix="",
    tags=["Agents"],
)

# Include conversation history routes
router.include_router(
    conversations.router,
    prefix="",
    tags=["Conversations"],
)

# Include orchestration routes (intelligent routing, handoffs)
router.include_router(
    orchestration.router,
    prefix="",
    tags=["Orchestration"],
)
