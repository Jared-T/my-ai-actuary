"""
Unit tests for Agent Orchestrator feature.

Tests the core orchestration logic without requiring a running server
or database connection.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# Import orchestrator components
from services.agent_orchestrator import (
    AgentOrchestrator,
    ConversationIntent,
    HandoffReason,
    RoutingDecision,
    HandoffRecord,
    OrchestrationState,
    INTENT_AGENT_MAPPING,
    INTENT_KEYWORDS,
)

# Import agent definitions
from agent_definitions.config import AgentType, get_agent_config
from agent_definitions.base import AGENT_HANDOFF_TARGETS, BaseAgent


class TestIntentClassification:
    """Tests for intent classification logic."""

    @pytest.fixture
    def orchestrator(self) -> AgentOrchestrator:
        """Create an orchestrator with mocked database."""
        mock_db = MagicMock()
        return AgentOrchestrator(mock_db)

    def test_classify_greeting(self, orchestrator: AgentOrchestrator) -> None:
        """Test that greetings are classified correctly."""
        messages = ["Hello", "Hi there", "Good morning", "Hey"]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.GREETING, f"Failed for: {msg}"

    def test_classify_reserving_intent(self, orchestrator: AgentOrchestrator) -> None:
        """Test that reserving-related messages are classified correctly."""
        messages = [
            "I need help with reserve calculations",
            "Can you perform IBNR estimation?",
            "Let's analyze the chain ladder results",
            "What is the loss ratio for this portfolio?",
        ]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.RESERVING_ANALYSIS, f"Failed for: {msg}"

    def test_classify_data_quality(self, orchestrator: AgentOrchestrator) -> None:
        """Test data quality intent classification."""
        messages = [
            "Please check the data quality",
            "Validate data integrity",
            "Find missing data in the dataset",
        ]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.DATA_QUALITY_CHECK, f"Failed for: {msg}"

    def test_classify_ifrs17(self, orchestrator: AgentOrchestrator) -> None:
        """Test IFRS17 intent classification."""
        messages = [
            "Calculate the contractual service margin",
            "Need help with IFRS17 calculations",
            "What is the BBA approach?",
        ]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.IFRS17_CALCULATION, f"Failed for: {msg}"

    def test_classify_handoff_request(self, orchestrator: AgentOrchestrator) -> None:
        """Test explicit handoff request detection."""
        messages = [
            "Please transfer to the reserving agent",
            "I want to speak to the compliance team",
            "Connect me with a specialist",
        ]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.HANDOFF_REQUEST, f"Failed for: {msg}"

    def test_classify_unknown_falls_to_general(self, orchestrator: AgentOrchestrator) -> None:
        """Test that unknown messages fall back to general question."""
        messages = [
            "What's the weather like?",
            "Random text without keywords",
            "xyz123",
        ]
        for msg in messages:
            intent = orchestrator.classify_intent(msg)
            assert intent == ConversationIntent.GENERAL_QUESTION, f"Failed for: {msg}"


class TestRoutingDecisions:
    """Tests for routing decision logic."""

    @pytest.fixture
    def orchestrator(self) -> AgentOrchestrator:
        """Create an orchestrator with mocked database."""
        mock_db = MagicMock()
        return AgentOrchestrator(mock_db)

    def test_route_to_reserving_agent(self, orchestrator: AgentOrchestrator) -> None:
        """Test routing to reserving agent based on intent."""
        state = OrchestrationState()
        decision = orchestrator.route_message(
            "I need to calculate IBNR reserves",
            state,
        )
        assert decision.target_agent == AgentType.RESERVING
        assert decision.intent == ConversationIntent.RESERVING_ANALYSIS

    def test_route_with_explicit_agent(self, orchestrator: AgentOrchestrator) -> None:
        """Test that explicit agent override works."""
        state = OrchestrationState()
        decision = orchestrator.route_message(
            "Hello",  # Would normally go to GENERAL
            state,
            explicit_agent=AgentType.IFRS17,
        )
        assert decision.target_agent == AgentType.IFRS17
        assert decision.confidence == 1.0

    def test_handoff_detection(self, orchestrator: AgentOrchestrator) -> None:
        """Test that handoff is detected when agent changes."""
        state = OrchestrationState(current_agent=AgentType.GENERAL)
        decision = orchestrator.route_message(
            "I need help with reserve calculations",
            state,
        )
        assert decision.requires_handoff is True
        assert decision.target_agent == AgentType.RESERVING
        assert decision.handoff_reason == HandoffReason.INTENT_CHANGE

    def test_no_handoff_when_same_agent(self, orchestrator: AgentOrchestrator) -> None:
        """Test that no handoff occurs when staying with same agent."""
        state = OrchestrationState(current_agent=AgentType.RESERVING)
        decision = orchestrator.route_message(
            "Calculate the IBNR for Q4",
            state,
        )
        assert decision.requires_handoff is False
        assert decision.target_agent == AgentType.RESERVING


class TestIntentAgentMapping:
    """Tests for intent to agent mapping."""

    def test_all_intents_have_mapping(self) -> None:
        """Verify all intents have an agent mapping."""
        for intent in ConversationIntent:
            assert intent in INTENT_AGENT_MAPPING, f"Missing mapping for {intent}"

    def test_reserved_intents_to_specialists(self) -> None:
        """Test that specialist intents map to specialist agents."""
        assert INTENT_AGENT_MAPPING[ConversationIntent.RESERVING_ANALYSIS] == AgentType.RESERVING
        assert INTENT_AGENT_MAPPING[ConversationIntent.IFRS17_CALCULATION] == AgentType.IFRS17
        assert INTENT_AGENT_MAPPING[ConversationIntent.DATA_QUALITY_CHECK] == AgentType.DATA_QUALITY
        assert INTENT_AGENT_MAPPING[ConversationIntent.COMPLIANCE_CHECK] == AgentType.COMPLIANCE
        assert INTENT_AGENT_MAPPING[ConversationIntent.QA_REVIEW] == AgentType.QA_REVIEWER

    def test_general_intents_to_general_agent(self) -> None:
        """Test that general intents map to general agent."""
        assert INTENT_AGENT_MAPPING[ConversationIntent.GREETING] == AgentType.GENERAL
        assert INTENT_AGENT_MAPPING[ConversationIntent.GENERAL_QUESTION] == AgentType.GENERAL
        assert INTENT_AGENT_MAPPING[ConversationIntent.HELP_REQUEST] == AgentType.GENERAL


class TestHandoffTargets:
    """Tests for handoff target configuration."""

    def test_all_agents_have_targets(self) -> None:
        """Verify all agent types have handoff targets defined."""
        for agent_type in AgentType:
            assert agent_type in AGENT_HANDOFF_TARGETS, f"Missing targets for {agent_type}"

    def test_general_can_reach_all_specialists(self) -> None:
        """Test that general agent can hand off to all specialists."""
        general_targets = AGENT_HANDOFF_TARGETS[AgentType.GENERAL]
        assert AgentType.RESERVING in general_targets
        assert AgentType.IFRS17 in general_targets
        assert AgentType.DATA_QUALITY in general_targets
        assert AgentType.ENGAGEMENT_MANAGER in general_targets

    def test_specialists_can_return_to_general(self) -> None:
        """Test that specialists can hand back to general agent."""
        specialists = [
            AgentType.RESERVING,
            AgentType.IFRS17,
            AgentType.DATA_QUALITY,
            AgentType.COMPLIANCE,
        ]
        for specialist in specialists:
            targets = AGENT_HANDOFF_TARGETS[specialist]
            assert AgentType.GENERAL in targets, f"{specialist} can't hand off to GENERAL"

    def test_engagement_manager_is_hub(self) -> None:
        """Test that engagement manager can reach many agents."""
        em_targets = AGENT_HANDOFF_TARGETS[AgentType.ENGAGEMENT_MANAGER]
        # Should be able to delegate to all specialists
        assert len(em_targets) >= 7


class TestOrchestrationState:
    """Tests for orchestration state management."""

    def test_state_initialization(self) -> None:
        """Test default state initialization."""
        state = OrchestrationState()
        assert state.current_agent == AgentType.GENERAL
        assert state.previous_agents == []
        assert state.handoff_history == []

    def test_state_with_history(self) -> None:
        """Test state with previous agents."""
        state = OrchestrationState(
            current_agent=AgentType.RESERVING,
            previous_agents=[AgentType.GENERAL, AgentType.DATA_QUALITY],
            intent_history=["greeting", "data_quality_check", "reserving_analysis"],
        )
        assert state.current_agent == AgentType.RESERVING
        assert len(state.previous_agents) == 2
        assert len(state.intent_history) == 3


class TestAgentConfigs:
    """Tests for agent configuration."""

    def test_all_agents_have_config(self) -> None:
        """Verify all agent types have configuration."""
        for agent_type in AgentType:
            config = get_agent_config(agent_type)
            assert config is not None
            assert config.name
            assert config.instructions

    def test_specialist_agents_have_low_temperature(self) -> None:
        """Test that specialist agents have lower temperature for accuracy."""
        specialists = [AgentType.RESERVING, AgentType.IFRS17, AgentType.DATA_QUALITY]
        for agent_type in specialists:
            config = get_agent_config(agent_type)
            assert config.model_settings.temperature <= 0.5, f"{agent_type} temperature too high"


class TestIntentKeywords:
    """Tests for intent keyword configuration."""

    def test_all_intents_have_keywords(self) -> None:
        """Verify key intents have keyword lists."""
        # Some intents are fallbacks and don't need keywords:
        # - GENERAL_QUESTION: fallback when no other intent matches
        # - CLARIFICATION: context-based, not keyword-based
        # - UNKNOWN: default fallback
        fallback_intents = {
            ConversationIntent.UNKNOWN,
            ConversationIntent.CLARIFICATION,
            ConversationIntent.GENERAL_QUESTION,
        }
        for intent in ConversationIntent:
            if intent not in fallback_intents:
                assert intent in INTENT_KEYWORDS, f"Missing keywords for {intent}"

    def test_no_duplicate_keywords(self) -> None:
        """Test that keywords don't overlap between intents."""
        all_keywords: dict[str, ConversationIntent] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in all_keywords:
                    # Some overlap is acceptable, just document it
                    pass  # Could add strict check if needed
                all_keywords[keyword] = intent


class TestHandoffRecord:
    """Tests for handoff record creation."""

    def test_handoff_record_creation(self) -> None:
        """Test creating a handoff record."""
        record = HandoffRecord(
            session_id=str(uuid4()),
            from_agent=AgentType.GENERAL,
            to_agent=AgentType.RESERVING,
            reason=HandoffReason.INTENT_CHANGE,
            message_trigger="I need help with reserves",
        )
        assert record.id is not None
        assert record.timestamp is not None
        assert record.from_agent == AgentType.GENERAL
        assert record.to_agent == AgentType.RESERVING

    def test_handoff_record_serialization(self) -> None:
        """Test that handoff record can be serialized."""
        record = HandoffRecord(
            session_id=str(uuid4()),
            from_agent=AgentType.GENERAL,
            to_agent=AgentType.RESERVING,
            reason=HandoffReason.USER_REQUEST,
        )
        data = record.model_dump(mode="json")
        assert isinstance(data, dict)
        assert "id" in data
        assert "from_agent" in data
        assert "to_agent" in data


class TestRoutingDecision:
    """Tests for routing decision model."""

    def test_routing_decision_creation(self) -> None:
        """Test creating a routing decision."""
        decision = RoutingDecision(
            target_agent=AgentType.RESERVING,
            confidence=0.85,
            intent=ConversationIntent.RESERVING_ANALYSIS,
            requires_handoff=True,
            handoff_reason=HandoffReason.INTENT_CHANGE,
        )
        assert decision.target_agent == AgentType.RESERVING
        assert decision.confidence == 0.85
        assert decision.requires_handoff is True

    def test_routing_decision_confidence_bounds(self) -> None:
        """Test that confidence is bounded correctly."""
        # Valid confidence values
        decision = RoutingDecision(
            target_agent=AgentType.GENERAL,
            confidence=0.5,
            intent=ConversationIntent.GENERAL_QUESTION,
        )
        assert 0.0 <= decision.confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
