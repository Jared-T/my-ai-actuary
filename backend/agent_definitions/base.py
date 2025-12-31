"""
Base agent class and registry for OpenAI Agents SDK integration.

Provides a base class for creating agents with consistent behavior,
and a registry for managing agent instances. Includes support for
agent handoffs and orchestration.
"""

from abc import ABC
from typing import Any, ClassVar

# Import from OpenAI Agents SDK
from agents import Agent, Runner, RunResult, trace

# Import from local agent_definitions module
from agent_definitions.config import AgentConfig, AgentType, get_agent_config, get_openai_api_key
from core.logging import get_logger

logger = get_logger(__name__)


# Define which agents can hand off to which other agents
# This creates a directed graph of allowed handoffs
AGENT_HANDOFF_TARGETS: dict[AgentType, list[AgentType]] = {
    AgentType.GENERAL: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.DATA_QUALITY,
        AgentType.RESERVING,
        AgentType.IFRS17,
        AgentType.ALM_REINSURANCE,
        AgentType.REPORTING,
        AgentType.PMO,
        AgentType.COMPLIANCE,
        AgentType.QA_REVIEWER,
    ],
    AgentType.ENGAGEMENT_MANAGER: [
        AgentType.DATA_QUALITY,
        AgentType.RESERVING,
        AgentType.IFRS17,
        AgentType.ALM_REINSURANCE,
        AgentType.REPORTING,
        AgentType.PMO,
        AgentType.COMPLIANCE,
        AgentType.QA_REVIEWER,
        AgentType.GENERAL,
    ],
    AgentType.DATA_QUALITY: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.RESERVING,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.RESERVING: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.DATA_QUALITY,
        AgentType.IFRS17,
        AgentType.QA_REVIEWER,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.IFRS17: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.RESERVING,
        AgentType.QA_REVIEWER,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.ALM_REINSURANCE: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.RESERVING,
        AgentType.QA_REVIEWER,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.REPORTING: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.QA_REVIEWER,
        AgentType.COMPLIANCE,
        AgentType.GENERAL,
    ],
    AgentType.PMO: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.COMPLIANCE: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.QA_REVIEWER,
        AgentType.REPORTING,
        AgentType.GENERAL,
    ],
    AgentType.QA_REVIEWER: [
        AgentType.ENGAGEMENT_MANAGER,
        AgentType.REPORTING,
        AgentType.COMPLIANCE,
        AgentType.GENERAL,
    ],
}


class BaseAgent(ABC):
    """
    Base class for all agents in the system.

    Provides common functionality for agent creation, configuration,
    and execution with the OpenAI Agents SDK.
    """

    agent_type: ClassVar[AgentType] = AgentType.GENERAL
    _config: AgentConfig
    _agent: Agent | None = None

    def __init__(
        self,
        config: AgentConfig | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """
        Initialize the base agent.

        Args:
            config: Optional custom configuration. Uses default if not provided.
            tools: Optional list of tools for the agent.
        """
        self._config = config or get_agent_config(self.agent_type)
        self._tools = tools or []
        self._agent = None
        logger.info(
            "Agent initialized",
            agent_type=self.agent_type.value,
            agent_name=self._config.name,
        )

    @property
    def config(self) -> AgentConfig:
        """Get the agent configuration."""
        return self._config

    @property
    def name(self) -> str:
        """Get the agent name."""
        return self._config.name

    def get_tools(self) -> list[Any]:
        """
        Get the tools available to this agent.

        Override in subclasses to provide agent-specific tools.
        """
        return self._tools

    def get_handoffs(self) -> list[Agent]:
        """
        Get the agents this agent can hand off to.

        Override in subclasses to define handoff relationships.
        Returns a list of Agent instances that this agent can transfer to.
        """
        return []

    def get_allowed_handoff_targets(self) -> list[AgentType]:
        """
        Get the agent types this agent is allowed to hand off to.

        Returns:
            List of AgentType enums that are valid handoff targets
        """
        return AGENT_HANDOFF_TARGETS.get(self.agent_type, [])

    def can_handoff_to(self, target_type: AgentType) -> bool:
        """
        Check if this agent can hand off to a specific agent type.

        Args:
            target_type: The target agent type to check

        Returns:
            True if handoff is allowed, False otherwise
        """
        return target_type in self.get_allowed_handoff_targets()

    @classmethod
    def get_handoff_graph(cls) -> dict[str, list[str]]:
        """
        Get the full handoff graph as a dictionary.

        Returns:
            Dictionary mapping agent type values to lists of allowed target type values
        """
        return {
            agent_type.value: [target.value for target in targets]
            for agent_type, targets in AGENT_HANDOFF_TARGETS.items()
        }

    def build_agent(self) -> Agent:
        """
        Build and return the OpenAI Agents SDK Agent instance.

        Returns:
            Configured Agent instance
        """
        if self._agent is None:
            self._agent = Agent(
                name=self._config.name,
                instructions=self._config.instructions,
                model=self._config.model_settings.model,
                tools=self.get_tools(),
                handoffs=self.get_handoffs(),
            )
            logger.debug(
                "Agent built",
                agent_name=self._config.name,
                model=self._config.model_settings.model,
                num_tools=len(self.get_tools()),
                num_handoffs=len(self.get_handoffs()),
            )
        return self._agent

    async def run(
        self,
        input_text: str,
        context: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> RunResult:
        """
        Run the agent with the given input.

        Args:
            input_text: The user input text
            context: Optional context dictionary
            trace_id: Optional trace ID for correlation

        Returns:
            RunResult from the agent execution
        """
        agent = self.build_agent()

        # Apply guardrails
        self._validate_input(input_text)

        logger.info(
            "Running agent",
            agent_name=self.name,
            input_length=len(input_text),
            trace_id=trace_id,
        )

        try:
            # Run with tracing if trace_id provided
            if trace_id and self._config.tracing.enabled:
                with trace(
                    workflow_name=self._config.tracing.workflow_name or self.name,
                    trace_id=trace_id,
                    group_id=self._config.tracing.group_id,
                ):
                    result = await Runner.run(agent, input_text)
            else:
                result = await Runner.run(agent, input_text)

            logger.info(
                "Agent run completed",
                agent_name=self.name,
                trace_id=trace_id,
            )
            return result

        except Exception as exc:
            logger.error(
                "Agent run failed",
                agent_name=self.name,
                error=str(exc),
                trace_id=trace_id,
                exc_info=True,
            )
            raise

    def _validate_input(self, input_text: str) -> None:
        """
        Validate input against guardrails.

        Args:
            input_text: The input text to validate

        Raises:
            ValueError: If input fails validation
        """
        max_length = self._config.guardrails.max_input_length
        if len(input_text) > max_length:
            raise ValueError(
                f"Input exceeds maximum length of {max_length} characters"
            )


class AgentRegistry:
    """
    Registry for managing agent instances.

    Provides singleton management and lookup for agents.
    """

    _agents: dict[AgentType, BaseAgent] = {}
    _custom_agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """
        Register an agent instance.

        Args:
            agent: The agent to register
        """
        cls._agents[agent.agent_type] = agent
        logger.info(
            "Agent registered",
            agent_type=agent.agent_type.value,
            agent_name=agent.name,
        )

    @classmethod
    def register_custom(cls, name: str, agent: BaseAgent) -> None:
        """
        Register a custom-named agent.

        Args:
            name: Custom name for the agent
            agent: The agent to register
        """
        cls._custom_agents[name] = agent
        logger.info("Custom agent registered", name=name, agent_name=agent.name)

    @classmethod
    def get(cls, agent_type: AgentType) -> BaseAgent | None:
        """
        Get a registered agent by type.

        Args:
            agent_type: The type of agent to retrieve

        Returns:
            The registered agent or None if not found
        """
        return cls._agents.get(agent_type)

    @classmethod
    def get_custom(cls, name: str) -> BaseAgent | None:
        """
        Get a custom-named agent.

        Args:
            name: The custom name of the agent

        Returns:
            The registered agent or None if not found
        """
        return cls._custom_agents.get(name)

    @classmethod
    def get_or_create(
        cls,
        agent_type: AgentType,
        agent_class: type[BaseAgent] | None = None,
        **kwargs: Any,
    ) -> BaseAgent:
        """
        Get an existing agent or create a new one.

        Args:
            agent_type: The type of agent
            agent_class: Optional class to use for creation
            **kwargs: Additional arguments for agent creation

        Returns:
            The agent instance
        """
        if agent_type in cls._agents:
            return cls._agents[agent_type]

        if agent_class is None:
            # Use a generic agent with default config
            agent = GenericAgent(agent_type=agent_type, **kwargs)
        else:
            agent = agent_class(**kwargs)

        cls.register(agent)
        return agent

    @classmethod
    def list_agents(cls) -> list[dict[str, Any]]:
        """
        List all registered agents.

        Returns:
            List of agent information dictionaries
        """
        agents = []
        for agent_type, agent in cls._agents.items():
            agents.append({
                "type": agent_type.value,
                "name": agent.name,
                "model": agent.config.model_settings.model,
            })
        for name, agent in cls._custom_agents.items():
            agents.append({
                "custom_name": name,
                "type": agent.agent_type.value,
                "name": agent.name,
                "model": agent.config.model_settings.model,
            })
        return agents

    @classmethod
    def clear(cls) -> None:
        """Clear all registered agents."""
        cls._agents.clear()
        cls._custom_agents.clear()
        logger.info("Agent registry cleared")


class GenericAgent(BaseAgent):
    """
    Generic agent that can be configured for any agent type.

    Useful for creating agents dynamically without defining a specific class.
    """

    def __init__(
        self,
        agent_type: AgentType = AgentType.GENERAL,
        config: AgentConfig | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        """
        Initialize a generic agent.

        Args:
            agent_type: The type of agent to create
            config: Optional custom configuration
            tools: Optional list of tools
        """
        self.agent_type = agent_type
        super().__init__(config=config or get_agent_config(agent_type), tools=tools)
