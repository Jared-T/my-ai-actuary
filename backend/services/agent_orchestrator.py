"""
Agent orchestration service for intelligent message routing.

Provides an orchestration layer that:
- Routes messages to appropriate agents based on intent classification
- Manages agent lifecycle and state
- Handles agent handoffs with context preservation
- Maintains conversation flow across multi-agent interactions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_definitions.config import AgentType, get_agent_config
from core.exceptions import NotFoundError, ValidationError
from core.logging import get_logger
from models.session import Session
from services.agent_service import AgentService

logger = get_logger(__name__)

# Constants
MAX_MESSAGE_TRIGGER_LENGTH = 200  # Maximum length for truncated trigger messages
MAX_INTENT_HISTORY_LENGTH = 100  # Maximum number of intents to keep in history
MAX_PREVIOUS_AGENTS_IN_RESPONSE = 3  # Number of previous agents to include in response


class ConversationIntent(str, Enum):
    """Classified intents for routing decisions."""

    # General intents
    GREETING = "greeting"
    GENERAL_QUESTION = "general_question"
    HELP_REQUEST = "help_request"

    # Engagement/Project management
    PROJECT_MANAGEMENT = "project_management"
    ENGAGEMENT_MANAGEMENT = "engagement_management"

    # Technical actuarial intents
    DATA_QUALITY_CHECK = "data_quality_check"
    RESERVING_ANALYSIS = "reserving_analysis"
    IFRS17_CALCULATION = "ifrs17_calculation"
    ALM_ANALYSIS = "alm_analysis"
    REINSURANCE_ANALYSIS = "reinsurance_analysis"

    # Output/reporting intents
    REPORT_GENERATION = "report_generation"
    COMPLIANCE_CHECK = "compliance_check"
    QA_REVIEW = "qa_review"

    # Meta intents
    HANDOFF_REQUEST = "handoff_request"
    CLARIFICATION = "clarification"
    UNKNOWN = "unknown"


class HandoffReason(str, Enum):
    """Reasons for agent handoff."""

    INTENT_CHANGE = "intent_change"
    TASK_COMPLETION = "task_completion"
    SPECIALIZED_EXPERTISE = "specialized_expertise"
    USER_REQUEST = "user_request"
    ESCALATION = "escalation"
    APPROVAL_REQUIRED = "approval_required"


class RoutingDecision(BaseModel):
    """Result of routing analysis."""

    target_agent: AgentType = Field(description="The agent to route to")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for routing decision")
    intent: ConversationIntent = Field(description="Detected intent")
    requires_handoff: bool = Field(default=False, description="Whether this requires a handoff")
    handoff_reason: HandoffReason | None = Field(default=None, description="Reason for handoff")
    context_to_transfer: dict[str, Any] = Field(default_factory=dict, description="Context to pass to new agent")


class HandoffRecord(BaseModel):
    """Record of an agent handoff."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = Field(description="Session where handoff occurred")
    from_agent: AgentType | None = Field(description="Agent handing off")
    to_agent: AgentType = Field(description="Agent receiving handoff")
    reason: HandoffReason = Field(description="Reason for handoff")
    context_transferred: dict[str, Any] = Field(default_factory=dict)
    message_trigger: str | None = Field(default=None, description="Message that triggered handoff")


class OrchestrationState(BaseModel):
    """State tracking for orchestration within a session."""

    current_agent: AgentType = Field(default=AgentType.GENERAL)
    previous_agents: list[AgentType] = Field(default_factory=list)
    handoff_history: list[dict[str, Any]] = Field(default_factory=list)
    intent_history: list[str] = Field(default_factory=list)
    accumulated_context: dict[str, Any] = Field(default_factory=dict)
    last_routing_decision: dict[str, Any] | None = Field(default=None)


# Intent to agent mapping for routing decisions
INTENT_AGENT_MAPPING: dict[ConversationIntent, AgentType] = {
    ConversationIntent.GREETING: AgentType.GENERAL,
    ConversationIntent.GENERAL_QUESTION: AgentType.GENERAL,
    ConversationIntent.HELP_REQUEST: AgentType.GENERAL,
    ConversationIntent.PROJECT_MANAGEMENT: AgentType.PMO,
    ConversationIntent.ENGAGEMENT_MANAGEMENT: AgentType.ENGAGEMENT_MANAGER,
    ConversationIntent.DATA_QUALITY_CHECK: AgentType.DATA_QUALITY,
    ConversationIntent.RESERVING_ANALYSIS: AgentType.RESERVING,
    ConversationIntent.IFRS17_CALCULATION: AgentType.IFRS17,
    ConversationIntent.ALM_ANALYSIS: AgentType.ALM_REINSURANCE,
    ConversationIntent.REINSURANCE_ANALYSIS: AgentType.ALM_REINSURANCE,
    ConversationIntent.REPORT_GENERATION: AgentType.REPORTING,
    ConversationIntent.COMPLIANCE_CHECK: AgentType.COMPLIANCE,
    ConversationIntent.QA_REVIEW: AgentType.QA_REVIEWER,
    ConversationIntent.HANDOFF_REQUEST: AgentType.ENGAGEMENT_MANAGER,
    ConversationIntent.CLARIFICATION: AgentType.GENERAL,
    ConversationIntent.UNKNOWN: AgentType.GENERAL,
}

# Keywords for simple intent detection (used as fallback)
INTENT_KEYWORDS: dict[ConversationIntent, list[str]] = {
    ConversationIntent.GREETING: ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"],
    ConversationIntent.DATA_QUALITY_CHECK: ["data quality", "data validation", "validate data", "check data", "data integrity", "data anomaly", "missing data", "data cleansing"],
    ConversationIntent.RESERVING_ANALYSIS: ["reserve", "reserving", "ibnr", "chain ladder", "loss ratio", "triangle", "claims reserve", "ultimate loss"],
    ConversationIntent.IFRS17_CALCULATION: ["ifrs17", "ifrs 17", "bba", "paa", "csm", "contractual service margin", "risk adjustment", "building block"],
    ConversationIntent.ALM_ANALYSIS: ["alm", "asset liability", "duration", "convexity", "matching", "liability matching"],
    ConversationIntent.REINSURANCE_ANALYSIS: ["reinsurance", "treaty", "cession", "retention", "excess of loss", "quota share", "proportional"],
    ConversationIntent.REPORT_GENERATION: ["report", "generate report", "create report", "summary", "documentation", "output"],
    ConversationIntent.COMPLIANCE_CHECK: ["compliance", "regulatory", "standards", "audit", "governance", "regulation"],
    ConversationIntent.QA_REVIEW: ["review", "qa", "quality assurance", "peer review", "check work", "validate results"],
    ConversationIntent.PROJECT_MANAGEMENT: ["project", "milestone", "deadline", "schedule", "resource", "status update", "timeline"],
    ConversationIntent.ENGAGEMENT_MANAGEMENT: ["engagement", "client", "deliverable", "scope", "workflow", "coordinate"],
    ConversationIntent.HELP_REQUEST: ["help", "how do i", "how to", "can you help", "assist me", "guide me"],
    ConversationIntent.HANDOFF_REQUEST: ["transfer to", "speak to", "connect me with", "hand off to", "switch to"],
}


class AgentOrchestrator:
    """
    Orchestrator for routing messages to appropriate agents.

    Manages agent lifecycle, handles handoffs, and maintains
    conversation state across multi-agent interactions.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the orchestrator.

        Args:
            db: Database session for persistence
        """
        self.db = db
        self.agent_service = AgentService(db)
        logger.info("AgentOrchestrator initialized")

    async def get_orchestration_state(
        self, session_id: UUID, user_id: UUID | None = None
    ) -> OrchestrationState:
        """
        Get the orchestration state for a session.

        Args:
            session_id: The session ID
            user_id: Optional user ID for ownership verification

        Returns:
            OrchestrationState for the session

        Raises:
            NotFoundError: If session not found or user doesn't own the session
        """
        stmt = select(Session).where(Session.id == session_id, Session.is_deleted == False)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError("Session", str(session_id))

        # Verify session ownership if user_id is provided
        if user_id is not None and session.user_id != user_id:
            raise NotFoundError("Session", str(session_id))

        context = session.context or {}
        orchestration_data = context.get("orchestration", {})

        return OrchestrationState(
            current_agent=AgentType(orchestration_data.get("current_agent", "general")),
            previous_agents=[AgentType(a) for a in orchestration_data.get("previous_agents", [])],
            handoff_history=orchestration_data.get("handoff_history", []),
            intent_history=orchestration_data.get("intent_history", []),
            accumulated_context=orchestration_data.get("accumulated_context", {}),
            last_routing_decision=orchestration_data.get("last_routing_decision"),
        )

    async def save_orchestration_state(
        self,
        session_id: UUID,
        state: OrchestrationState,
    ) -> None:
        """
        Save the orchestration state for a session.

        Args:
            session_id: The session ID
            state: The orchestration state to save
        """
        stmt = select(Session).where(Session.id == session_id, Session.is_deleted == False)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError("Session", str(session_id))

        context = session.context or {}
        context["orchestration"] = {
            "current_agent": state.current_agent.value,
            "previous_agents": [a.value for a in state.previous_agents],
            "handoff_history": state.handoff_history,
            "intent_history": state.intent_history,
            "accumulated_context": state.accumulated_context,
            "last_routing_decision": state.last_routing_decision,
        }
        session.context = context
        await self.db.flush()

    def classify_intent(self, message: str, context: dict[str, Any] | None = None) -> ConversationIntent:
        """
        Classify the intent of a message.

        Uses keyword-based classification with context awareness.
        In production, this could be enhanced with ML-based classification.

        Args:
            message: The message to classify
            context: Optional conversation context

        Returns:
            Classified ConversationIntent
        """
        message_lower = message.lower().strip()

        # Check for explicit handoff requests first
        for keyword in INTENT_KEYWORDS[ConversationIntent.HANDOFF_REQUEST]:
            if keyword in message_lower:
                return ConversationIntent.HANDOFF_REQUEST

        # Score each intent based on keyword matches
        intent_scores: dict[ConversationIntent, float] = {}

        for intent, keywords in INTENT_KEYWORDS.items():
            score = 0.0
            for keyword in keywords:
                if keyword in message_lower:
                    # Longer keywords get higher weight
                    score += len(keyword.split()) * 0.3
            intent_scores[intent] = score

        # Get the highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores, key=lambda k: intent_scores[k])
            if intent_scores[best_intent] > 0:
                return best_intent

        # Use context to make better decisions if available
        if context:
            current_agent = context.get("current_agent")
            if current_agent:
                # If we have a current agent and no clear intent change,
                # assume continuation of current topic
                return ConversationIntent.CLARIFICATION

        return ConversationIntent.GENERAL_QUESTION

    def route_message(
        self,
        message: str,
        current_state: OrchestrationState,
        explicit_agent: AgentType | None = None,
    ) -> RoutingDecision:
        """
        Determine which agent should handle a message.

        Args:
            message: The user message
            current_state: Current orchestration state
            explicit_agent: Optional explicit agent override

        Returns:
            RoutingDecision with target agent and metadata
        """
        # If explicit agent is specified, use it
        if explicit_agent:
            requires_handoff = explicit_agent != current_state.current_agent
            return RoutingDecision(
                target_agent=explicit_agent,
                confidence=1.0,
                intent=ConversationIntent.HANDOFF_REQUEST if requires_handoff else ConversationIntent.GENERAL_QUESTION,
                requires_handoff=requires_handoff,
                handoff_reason=HandoffReason.USER_REQUEST if requires_handoff else None,
            )

        # Classify intent
        context = {"current_agent": current_state.current_agent.value}
        intent = self.classify_intent(message, context)

        # Get target agent from intent mapping
        target_agent = INTENT_AGENT_MAPPING.get(intent, AgentType.GENERAL)

        # Determine confidence based on intent clarity
        confidence = 0.8 if intent != ConversationIntent.UNKNOWN else 0.5

        # Check if handoff is needed
        requires_handoff = target_agent != current_state.current_agent
        handoff_reason = None

        if requires_handoff:
            if intent == ConversationIntent.HANDOFF_REQUEST:
                handoff_reason = HandoffReason.USER_REQUEST
            else:
                handoff_reason = HandoffReason.INTENT_CHANGE

        # Build context to transfer
        context_to_transfer = {
            "previous_agent": current_state.current_agent.value,
            "conversation_summary": f"Previous agent: {current_state.current_agent.value}",
            "intent_history": current_state.intent_history[-5:] if current_state.intent_history else [],
        }

        return RoutingDecision(
            target_agent=target_agent,
            confidence=confidence,
            intent=intent,
            requires_handoff=requires_handoff,
            handoff_reason=handoff_reason,
            context_to_transfer=context_to_transfer if requires_handoff else {},
        )

    async def execute_handoff(
        self,
        session_id: UUID,
        state: OrchestrationState,
        decision: RoutingDecision,
        message: str,
    ) -> HandoffRecord:
        """
        Execute an agent handoff.

        Args:
            session_id: The session ID
            state: Current orchestration state
            decision: The routing decision
            message: The message that triggered the handoff

        Returns:
            HandoffRecord documenting the handoff
        """
        record = HandoffRecord(
            session_id=str(session_id),
            from_agent=state.current_agent,
            to_agent=decision.target_agent,
            reason=decision.handoff_reason or HandoffReason.INTENT_CHANGE,
            context_transferred=decision.context_to_transfer,
            message_trigger=message[:MAX_MESSAGE_TRIGGER_LENGTH] if message else None,
        )

        # Update state
        state.previous_agents.append(state.current_agent)
        state.current_agent = decision.target_agent
        state.handoff_history.append(record.model_dump(mode="json"))

        logger.info(
            "Handoff executed",
            session_id=str(session_id),
            from_agent=record.from_agent.value if record.from_agent else None,
            to_agent=record.to_agent.value,
            reason=record.reason.value,
        )

        return record

    async def orchestrate(
        self,
        user_id: UUID,
        message: str,
        session_id: UUID | None = None,
        engagement_id: UUID | None = None,
        explicit_agent: AgentType | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Main orchestration entry point.

        Routes messages to appropriate agents, handles handoffs,
        and maintains conversation state.

        Args:
            user_id: The user's ID
            message: The user's message
            session_id: Optional existing session ID
            engagement_id: Optional engagement ID
            explicit_agent: Optional explicit agent override
            context: Optional additional context

        Returns:
            Dictionary with response and orchestration metadata
        """
        if not message or not message.strip():
            raise ValidationError("Message cannot be empty")

        trace_id = str(uuid4())

        # Get or create session
        session = await self.agent_service.get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            engagement_id=engagement_id,
        )

        # Get or initialize orchestration state
        try:
            state = await self.get_orchestration_state(session.id)
        except NotFoundError:
            state = OrchestrationState()

        # Make routing decision
        decision = self.route_message(message, state, explicit_agent)

        # Execute handoff if needed
        handoff_record = None
        if decision.requires_handoff:
            handoff_record = await self.execute_handoff(
                session.id,
                state,
                decision,
                message,
            )

        # Update state with routing decision
        state.intent_history.append(decision.intent.value)
        # Limit intent history to prevent unbounded growth
        if len(state.intent_history) > MAX_INTENT_HISTORY_LENGTH:
            state.intent_history = state.intent_history[-MAX_INTENT_HISTORY_LENGTH:]
        state.last_routing_decision = decision.model_dump(mode="json")

        # Save orchestration state
        await self.save_orchestration_state(session.id, state)

        # Run the agent via agent service
        result = await self.agent_service.run_agent(
            user_id=user_id,
            message=message,
            agent_type=decision.target_agent,
            session_id=session.id,
            engagement_id=engagement_id,
            context=context,
        )

        # Enrich result with orchestration metadata
        result["orchestration"] = {
            "routing_decision": {
                "target_agent": decision.target_agent.value,
                "confidence": decision.confidence,
                "intent": decision.intent.value,
            },
            "handoff_occurred": decision.requires_handoff,
            "handoff_record": handoff_record.model_dump(mode="json") if handoff_record else None,
            "current_state": {
                "current_agent": state.current_agent.value,
                "previous_agents": [a.value for a in state.previous_agents[-MAX_PREVIOUS_AGENTS_IN_RESPONSE:]],
            },
        }

        logger.info(
            "Orchestration completed",
            session_id=str(session.id),
            agent_type=decision.target_agent.value,
            intent=decision.intent.value,
            handoff_occurred=decision.requires_handoff,
            trace_id=trace_id,
        )

        return result

    async def get_session_orchestration_history(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> dict[str, Any]:
        """
        Get the orchestration history for a session.

        Args:
            user_id: The user's ID
            session_id: The session ID

        Returns:
            Dictionary with orchestration state and history
        """
        state = await self.get_orchestration_state(session_id, user_id)

        return {
            "session_id": str(session_id),
            "current_agent": state.current_agent.value,
            "previous_agents": [a.value for a in state.previous_agents],
            "handoff_count": len(state.handoff_history),
            "handoff_history": state.handoff_history,
            "intent_history": state.intent_history,
            "accumulated_context": state.accumulated_context,
            "last_routing_decision": state.last_routing_decision,
        }

    async def force_handoff(
        self,
        user_id: UUID,
        session_id: UUID,
        target_agent: AgentType,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Force a handoff to a specific agent.

        Args:
            user_id: The user's ID
            session_id: The session ID
            target_agent: The agent to hand off to
            reason: Optional reason for the handoff

        Returns:
            Dictionary with handoff result
        """
        state = await self.get_orchestration_state(session_id, user_id)

        decision = RoutingDecision(
            target_agent=target_agent,
            confidence=1.0,
            intent=ConversationIntent.HANDOFF_REQUEST,
            requires_handoff=True,
            handoff_reason=HandoffReason.USER_REQUEST,
            context_to_transfer={
                "previous_agent": state.current_agent.value,
                "reason": reason,
            },
        )

        handoff_record = await self.execute_handoff(
            session_id,
            state,
            decision,
            f"Forced handoff: {reason}" if reason else "Forced handoff",
        )

        await self.save_orchestration_state(session_id, state)

        return {
            "session_id": str(session_id),
            "handoff_record": handoff_record.model_dump(mode="json"),
            "new_agent": target_agent.value,
            "previous_agent": handoff_record.from_agent.value if handoff_record.from_agent else None,
        }

    def list_available_agents_for_handoff(self) -> list[dict[str, Any]]:
        """
        List all agents available for handoff.

        Returns:
            List of agent info for handoff selection
        """
        agents = []
        for agent_type in AgentType:
            config = get_agent_config(agent_type)
            agents.append({
                "type": agent_type.value,
                "name": config.name,
                "description": config.instructions[:150] + "..." if len(config.instructions) > 150 else config.instructions,
                "capabilities": self._get_agent_capabilities(agent_type),
            })
        return agents

    def _get_agent_capabilities(self, agent_type: AgentType) -> list[str]:
        """Get a list of capabilities for an agent type."""
        capabilities_map = {
            AgentType.GENERAL: ["General Q&A", "Platform guidance", "Concept explanation"],
            AgentType.ENGAGEMENT_MANAGER: ["Project coordination", "Agent delegation", "Workflow management"],
            AgentType.DATA_QUALITY: ["Data validation", "Anomaly detection", "Data cleansing recommendations"],
            AgentType.RESERVING: ["Chain ladder analysis", "IBNR estimation", "Loss ratio analysis"],
            AgentType.IFRS17: ["BBA calculations", "PAA calculations", "CSM analysis"],
            AgentType.ALM_REINSURANCE: ["Asset-liability matching", "Reinsurance analysis", "Duration analysis"],
            AgentType.REPORTING: ["Report generation", "Executive summaries", "Documentation"],
            AgentType.PMO: ["Project tracking", "Resource allocation", "Status reporting"],
            AgentType.COMPLIANCE: ["Regulatory compliance", "Standards review", "Governance"],
            AgentType.QA_REVIEWER: ["Calculation review", "Methodology validation", "Peer review"],
        }
        return capabilities_map.get(agent_type, ["General assistance"])


# Dependency injection helper for FastAPI
async def get_orchestrator(db: AsyncSession) -> AgentOrchestrator:
    """
    FastAPI dependency for getting an AgentOrchestrator instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured AgentOrchestrator instance
    """
    return AgentOrchestrator(db)
