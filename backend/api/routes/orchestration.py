"""
Orchestration API routes for intelligent agent routing.

Provides endpoints for:
- Orchestrated message routing with intent detection
- Agent handoff management
- Orchestration state and history queries
- Handoff-eligible agent listings
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_definitions.config import AgentType
from core.auth import CurrentUser
from core.database import get_db
from core.exceptions import NotFoundError, ValidationError
from core.logging import get_logger
from services.agent_orchestrator import (
    AgentOrchestrator,
    ConversationIntent,
    HandoffReason,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/orchestration", tags=["Orchestration"])


# Request/Response Models
class OrchestrationRequest(BaseModel):
    """Request model for orchestrated message routing."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="The user message to process",
    )
    session_id: UUID | None = Field(
        default=None,
        description="Optional existing session ID to continue conversation",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Optional engagement ID to associate with",
    )
    explicit_agent: str | None = Field(
        default=None,
        description="Optional explicit agent type override (bypasses intent detection)",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional context for the agent",
    )


class RoutingInfo(BaseModel):
    """Information about the routing decision."""

    target_agent: str = Field(description="Agent type that handled the message")
    confidence: float = Field(description="Confidence score for routing decision")
    intent: str = Field(description="Detected intent")


class OrchestrationMetadata(BaseModel):
    """Orchestration metadata in response."""

    routing_decision: RoutingInfo = Field(description="Routing decision details")
    handoff_occurred: bool = Field(description="Whether a handoff occurred")
    handoff_record: dict[str, Any] | None = Field(
        default=None,
        description="Handoff record if one occurred",
    )
    current_state: dict[str, Any] = Field(description="Current orchestration state")


class OrchestrationResponse(BaseModel):
    """Response model for orchestrated message."""

    session_id: str = Field(description="Session ID for the conversation")
    trace_id: str = Field(description="Trace ID for debugging")
    agent_type: str = Field(description="Type of agent that responded")
    response: str = Field(description="The agent's response")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata",
    )
    orchestration: OrchestrationMetadata = Field(
        description="Orchestration-specific metadata",
    )


class HandoffRequest(BaseModel):
    """Request model for forcing an agent handoff."""

    target_agent: str = Field(
        ...,
        description="Target agent type to hand off to",
    )
    reason: str | None = Field(
        default=None,
        description="Optional reason for the handoff",
    )


class HandoffResponse(BaseModel):
    """Response model for handoff operation."""

    session_id: str = Field(description="Session ID")
    new_agent: str = Field(description="New active agent type")
    previous_agent: str | None = Field(description="Previous agent type")
    handoff_record: dict[str, Any] = Field(description="Handoff record details")


class OrchestrationHistoryResponse(BaseModel):
    """Response model for orchestration history."""

    session_id: str = Field(description="Session ID")
    current_agent: str = Field(description="Currently active agent")
    previous_agents: list[str] = Field(description="Previous agents in order")
    handoff_count: int = Field(description="Total number of handoffs")
    handoff_history: list[dict[str, Any]] = Field(description="Handoff records")
    intent_history: list[str] = Field(description="History of detected intents")
    accumulated_context: dict[str, Any] = Field(description="Accumulated context")
    last_routing_decision: dict[str, Any] | None = Field(
        description="Last routing decision"
    )


class AgentCapability(BaseModel):
    """Agent capability information."""

    type: str = Field(description="Agent type identifier")
    name: str = Field(description="Human-readable agent name")
    description: str = Field(description="Agent description")
    capabilities: list[str] = Field(description="List of agent capabilities")


class AvailableAgentsResponse(BaseModel):
    """Response model for available agents listing."""

    agents: list[AgentCapability] = Field(description="List of available agents")


class IntentInfo(BaseModel):
    """Information about an intent."""

    intent: str = Field(description="Intent identifier")
    description: str = Field(description="Intent description")
    default_agent: str = Field(description="Default agent for this intent")


class IntentsResponse(BaseModel):
    """Response model for available intents."""

    intents: list[IntentInfo] = Field(description="List of available intents")


# Helper to get valid agent type
def _validate_agent_type(agent_type_str: str) -> AgentType:
    """Validate and convert agent type string."""
    try:
        return AgentType(agent_type_str)
    except ValueError:
        valid_types = [t.value for t in AgentType]
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid agent type: {agent_type_str}. Valid types: {valid_types}",
                "valid_types": valid_types,
            },
        )


# Endpoints
@router.post(
    "/route",
    response_model=OrchestrationResponse,
    summary="Route message with orchestration",
    description="""
    Send a message through the orchestration layer for intelligent routing.

    The orchestrator will:
    1. Classify the message intent
    2. Determine the appropriate agent based on intent
    3. Handle any necessary agent handoffs
    4. Execute the agent and return the response

    Optionally specify an explicit_agent to bypass intent detection.
    """,
)
async def route_message(
    request: OrchestrationRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> OrchestrationResponse:
    """Route a message through the orchestration layer."""
    try:
        # Validate explicit agent if provided
        explicit_agent = None
        if request.explicit_agent:
            explicit_agent = _validate_agent_type(request.explicit_agent)

        orchestrator = AgentOrchestrator(db)
        result = await orchestrator.orchestrate(
            user_id=current_user.id,
            message=request.message,
            session_id=request.session_id,
            engagement_id=request.engagement_id,
            explicit_agent=explicit_agent,
            context=request.context,
        )

        # Build orchestration metadata
        orchestration_data = result.get("orchestration", {})
        routing_decision = orchestration_data.get("routing_decision", {})

        return OrchestrationResponse(
            session_id=result["session_id"],
            trace_id=result["trace_id"],
            agent_type=result["agent_type"],
            response=result["response"],
            metadata=result.get("metadata", {}),
            orchestration=OrchestrationMetadata(
                routing_decision=RoutingInfo(
                    target_agent=routing_decision.get("target_agent", result["agent_type"]),
                    confidence=routing_decision.get("confidence", 1.0),
                    intent=routing_decision.get("intent", "unknown"),
                ),
                handoff_occurred=orchestration_data.get("handoff_occurred", False),
                handoff_record=orchestration_data.get("handoff_record"),
                current_state=orchestration_data.get("current_state", {}),
            ),
        )
    except ValidationError as e:
        logger.warning("Validation error in route_message", error=str(e))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except NotFoundError as e:
        logger.warning("Resource not found in route_message", error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in route_message", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the message",
        )


@router.post(
    "/sessions/{session_id}/handoff",
    response_model=HandoffResponse,
    summary="Force agent handoff",
    description="Force a handoff to a specific agent within a session.",
)
async def force_handoff(
    session_id: UUID,
    request: HandoffRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> HandoffResponse:
    """Force a handoff to a specific agent."""
    try:
        target_agent = _validate_agent_type(request.target_agent)

        orchestrator = AgentOrchestrator(db)
        result = await orchestrator.force_handoff(
            user_id=current_user.id,
            session_id=session_id,
            target_agent=target_agent,
            reason=request.reason,
        )

        return HandoffResponse(
            session_id=result["session_id"],
            new_agent=result["new_agent"],
            previous_agent=result.get("previous_agent"),
            handoff_record=result["handoff_record"],
        )
    except NotFoundError as e:
        logger.warning("Session not found in force_handoff", session_id=str(session_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in force_handoff", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during handoff",
        )


@router.get(
    "/sessions/{session_id}/history",
    response_model=OrchestrationHistoryResponse,
    summary="Get orchestration history",
    description="Get the orchestration history for a specific session.",
)
async def get_orchestration_history(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> OrchestrationHistoryResponse:
    """Get orchestration history for a session."""
    try:
        orchestrator = AgentOrchestrator(db)
        history = await orchestrator.get_session_orchestration_history(
            user_id=current_user.id,
            session_id=session_id,
        )

        return OrchestrationHistoryResponse(
            session_id=history["session_id"],
            current_agent=history["current_agent"],
            previous_agents=history["previous_agents"],
            handoff_count=history["handoff_count"],
            handoff_history=history["handoff_history"],
            intent_history=history["intent_history"],
            accumulated_context=history["accumulated_context"],
            last_routing_decision=history.get("last_routing_decision"),
        )
    except NotFoundError as e:
        logger.warning("Session not found in get_orchestration_history", session_id=str(session_id), error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error in get_orchestration_history", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching orchestration history",
        )


@router.get(
    "/agents",
    response_model=AvailableAgentsResponse,
    summary="List agents for handoff",
    description="Get a list of all agents available for handoff with their capabilities.",
)
async def list_agents_for_handoff(
    db: AsyncSession = Depends(get_db),
) -> AvailableAgentsResponse:
    """List all agents available for handoff."""
    orchestrator = AgentOrchestrator(db)
    agents = orchestrator.list_available_agents_for_handoff()

    return AvailableAgentsResponse(
        agents=[AgentCapability(**agent) for agent in agents]
    )


@router.get(
    "/intents",
    response_model=IntentsResponse,
    summary="List available intents",
    description="Get a list of all intents the orchestrator can detect.",
)
async def list_intents() -> IntentsResponse:
    """List all available intents and their default agents."""
    from services.agent_orchestrator import INTENT_AGENT_MAPPING

    intent_descriptions = {
        ConversationIntent.GREETING: "General greeting or salutation",
        ConversationIntent.GENERAL_QUESTION: "General questions about actuarial concepts",
        ConversationIntent.HELP_REQUEST: "Request for help or guidance",
        ConversationIntent.PROJECT_MANAGEMENT: "Project management and tracking",
        ConversationIntent.ENGAGEMENT_MANAGEMENT: "Engagement coordination and workflow",
        ConversationIntent.DATA_QUALITY_CHECK: "Data validation and quality assessment",
        ConversationIntent.RESERVING_ANALYSIS: "Reserve estimation and analysis",
        ConversationIntent.IFRS17_CALCULATION: "IFRS17 accounting calculations",
        ConversationIntent.ALM_ANALYSIS: "Asset-liability management analysis",
        ConversationIntent.REINSURANCE_ANALYSIS: "Reinsurance treaty and structure analysis",
        ConversationIntent.REPORT_GENERATION: "Report creation and documentation",
        ConversationIntent.COMPLIANCE_CHECK: "Regulatory and standards compliance",
        ConversationIntent.QA_REVIEW: "Quality assurance and peer review",
        ConversationIntent.HANDOFF_REQUEST: "Explicit request to transfer to another agent",
        ConversationIntent.CLARIFICATION: "Clarification or follow-up question",
        ConversationIntent.UNKNOWN: "Unclassified intent",
    }

    intents = []
    for intent in ConversationIntent:
        default_agent = INTENT_AGENT_MAPPING.get(intent, AgentType.GENERAL)
        intents.append(
            IntentInfo(
                intent=intent.value,
                description=intent_descriptions.get(intent, "No description available"),
                default_agent=default_agent.value,
            )
        )

    return IntentsResponse(intents=intents)


@router.get(
    "/health",
    summary="Orchestration health check",
    description="Check if the orchestration service is operational.",
)
async def orchestration_health_check() -> dict[str, Any]:
    """Check orchestration service health."""
    from agent_definitions.config import AgentType, get_openai_api_key

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
        "available_intents": len(ConversationIntent),
        "service": "orchestration",
    }
