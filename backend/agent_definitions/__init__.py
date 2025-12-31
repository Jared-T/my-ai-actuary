"""
Agent definitions using OpenAI Agents SDK.

This module contains the AI agent implementations for:
- Engagement Manager
- Data Quality Agent
- Reserving Agent
- IFRS17 Agent
- ALM & Reinsurance Agent
- Reporting Agent
- PMO Agent
- Compliance Agent
- QA Reviewer
"""

from agent_definitions.config import (
    AgentConfig,
    AgentModelConfig,
    AgentTracingConfig,
    AgentType,
    GuardrailConfig,
    get_agent_config,
    get_openai_api_key,
)
from agent_definitions.base import (
    AGENT_HANDOFF_TARGETS,
    AgentRegistry,
    BaseAgent,
    GenericAgent,
)

__all__ = [
    # Config
    "AgentConfig",
    "AgentModelConfig",
    "AgentTracingConfig",
    "AgentType",
    "GuardrailConfig",
    "get_agent_config",
    "get_openai_api_key",
    # Base
    "AGENT_HANDOFF_TARGETS",
    "AgentRegistry",
    "BaseAgent",
    "GenericAgent",
]
