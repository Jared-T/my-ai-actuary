"""
Agent API routes for agent management and execution.

Provides endpoints for:
- Listing available agents
- Running agent conversations
- Managing chat sessions

This module demonstrates the new dependency injection system for user context
extraction and propagation throughout the request lifecycle.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agent_definitions.config import AgentType
from core.dependencies import (
    AuthenticatedContainerDep,
    ServiceContainerDep,
    UserContextDep,
)

router = APIRouter(prefix="/agents", tags=["Agents"])


# Request/Response Models
class AgentRunRequest(BaseModel):
    """Request model for running an agent."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="The user message to send to the agent",
    )
    agent_type: str = Field(
        default="general",
        description="Type of agent to use",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Optional existing session ID to continue conversation",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Optional engagement ID to associate with",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional context for the agent",
    )


class AgentRunResponse(BaseModel):
    """Response model for agent run."""

    session_id: str = Field(description="Session ID for the conversation")
    trace_id: str = Field(description="Trace ID for debugging")
    agent_type: str = Field(description="Type of agent that responded")
    response: str = Field(description="The agent's response")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata",
    )


class AgentInfo(BaseModel):
    """Information about an available agent."""

    type: str = Field(description="Agent type identifier")
    name: str = Field(description="Human-readable agent name")
    description: str = Field(description="Agent description/instructions summary")
    model: str = Field(description="LLM model used by the agent")


class AgentListResponse(BaseModel):
    """Response model for listing agents."""

    agents: list[AgentInfo] = Field(description="List of available agents")


class SessionMessage(BaseModel):
    """A message in a session."""

    id: str = Field(description="Message ID")
    role: str = Field(description="Message role (user, assistant, system, tool)")
    content: str = Field(description="Message content")
    created_at: str = Field(description="ISO timestamp of message creation")
    tool_name: str | None = Field(default=None, description="Tool name if applicable")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class SessionHistoryResponse(BaseModel):
    """Response model for session history."""

    id: str = Field(description="Session ID")
    title: str | None = Field(description="Session title")
    context: dict[str, Any] | None = Field(description="Session context")
    created_at: str = Field(description="Session creation timestamp")
    last_activity_at: str = Field(description="Last activity timestamp")
    messages: list[SessionMessage] = Field(description="Session messages")


class SessionSummary(BaseModel):
    """Summary of a session for listing."""

    id: str = Field(description="Session ID")
    title: str | None = Field(description="Session title")
    context: dict[str, Any] | None = Field(description="Session context")
    created_at: str = Field(description="Session creation timestamp")
    last_activity_at: str = Field(description="Last activity timestamp")
    message_count: int = Field(description="Number of messages in the session")


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    sessions: list[SessionSummary] = Field(description="List of user sessions")
    total: int = Field(description="Total number of sessions")


class UpdateSessionRequest(BaseModel):
    """Request model for updating a session."""

    title: str | None = Field(default=None, description="New session title")


# Endpoints
@router.get(
    "",
    response_model=AgentListResponse,
    summary="List available agents",
    description="Get a list of all available agent types with their configurations.",
)
async def list_agents(
    container: ServiceContainerDep,
) -> AgentListResponse:
    """List all available agent types using the service container (no auth required)."""
    service = container.get_agent_service()
    agents = await service.list_available_agents()
    return AgentListResponse(
        agents=[AgentInfo(**agent) for agent in agents]
    )


@router.post(
    "/run",
    response_model=AgentRunResponse,
    summary="Run an agent",
    description="Send a message to an agent and get a response. Creates or continues a session.",
)
async def run_agent(
    request: AgentRunRequest,
    user_ctx: UserContextDep,
    container: AuthenticatedContainerDep,
) -> AgentRunResponse:
    """
    Run an agent with a user message.

    This endpoint uses the new dependency injection system:
    1. UserContextDep provides authenticated user context with permissions
    2. AuthenticatedContainerDep provides access to services with user context
    3. Services are lazily initialized from the container
    4. User context flows through the entire request lifecycle
    """
    # Validate agent type
    try:
        agent_type = AgentType(request.agent_type)
    except ValueError:
        valid_types = [t.value for t in AgentType]
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid agent type: {request.agent_type}. Valid types: {valid_types}",
                "valid_types": valid_types,
            },
        )

    # Get service from container (lazy initialization with user context)
    service = container.get_agent_service()
    result = await service.run_agent(
        user_id=user_ctx.user_id,
        message=request.message,
        agent_type=agent_type,
        session_id=request.session_id,
        engagement_id=request.engagement_id,
        context=request.context,
    )

    return AgentRunResponse(**result)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List user sessions",
    description="Get a list of all sessions for the authenticated user.",
)
async def list_sessions(
    user_ctx: UserContextDep,
    container: AuthenticatedContainerDep,
    limit: int = Query(default=50, ge=1, le=100, description="Maximum sessions to return"),
    offset: int = Query(default=0, ge=0, description="Number of sessions to skip"),
) -> SessionListResponse:
    """
    List all sessions for the current user.

    Returns sessions ordered by last activity (most recent first).
    Uses the new DI system for user context propagation.
    """
    service = container.get_agent_service()
    result = await service.list_user_sessions(
        user_id=user_ctx.user_id,
        limit=limit,
        offset=offset,
    )
    return SessionListResponse(
        sessions=[SessionSummary(**s) for s in result["sessions"]],
        total=result["total"],
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionHistoryResponse,
    summary="Get session history",
    description="Get the message history for a specific session.",
)
async def get_session_history(
    session_id: UUID,
    user_ctx: UserContextDep,
    container: AuthenticatedContainerDep,
) -> SessionHistoryResponse:
    """Get the history for a specific session using the new DI system."""
    service = container.get_agent_service()
    history = await service.get_session_history(
        user_id=user_ctx.user_id,
        session_id=session_id,
    )
    return SessionHistoryResponse(
        id=history["id"],
        title=history["title"],
        context=history["context"],
        created_at=history["created_at"],
        last_activity_at=history["last_activity_at"],
        messages=[SessionMessage(**msg) for msg in history["messages"]],
    )


@router.patch(
    "/sessions/{session_id}",
    response_model=SessionSummary,
    summary="Update session",
    description="Update session properties like title.",
)
async def update_session(
    session_id: UUID,
    request: UpdateSessionRequest,
    user_ctx: UserContextDep,
    container: AuthenticatedContainerDep,
) -> SessionSummary:
    """Update a session's properties using the new DI system."""
    service = container.get_agent_service()
    result = await service.update_session(
        user_id=user_ctx.user_id,
        session_id=session_id,
        title=request.title,
    )
    return SessionSummary(**result)


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Delete session",
    description="Soft-delete a session and its messages.",
)
async def delete_session(
    session_id: UUID,
    user_ctx: UserContextDep,
    container: AuthenticatedContainerDep,
) -> None:
    """Soft-delete a session using the new DI system."""
    service = container.get_agent_service()
    await service.delete_session(
        user_id=user_ctx.user_id,
        session_id=session_id,
    )


@router.get(
    "/health",
    summary="Agent service health check",
    description="Check if the agent service is operational.",
)
async def agent_health_check() -> dict[str, Any]:
    """Check agent service health."""
    from agent_definitions.config import get_openai_api_key

    api_key_configured = False
    try:
        get_openai_api_key()
        api_key_configured = True
    except ValueError:
        pass

    return {
        "status": "healthy" if api_key_configured else "degraded",
        "api_key_configured": api_key_configured,
        "available_agents": len(AgentType),
    }
