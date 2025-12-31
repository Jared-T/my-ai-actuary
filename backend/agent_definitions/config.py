"""
Agent configuration and settings for OpenAI Agents SDK.

Provides centralized configuration for all agent instances including
model settings, tracing configuration, and default behaviors.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.config import settings


class AgentType(str, Enum):
    """Types of agents available in the system."""

    ENGAGEMENT_MANAGER = "engagement_manager"
    DATA_QUALITY = "data_quality"
    DATA_ACCESS = "data_access"
    RESERVING = "reserving"
    IFRS17 = "ifrs17"
    ALM_REINSURANCE = "alm_reinsurance"
    REPORTING = "reporting"
    PMO = "pmo"
    COMPLIANCE = "compliance"
    QA_REVIEWER = "qa_reviewer"
    GENERAL = "general"


class AgentModelConfig(BaseModel):
    """Configuration for agent model settings."""

    model: str = Field(
        default_factory=lambda: settings.openai_model,
        description="OpenAI model to use for this agent",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for model responses",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens for model response",
    )


class AgentTracingConfig(BaseModel):
    """Configuration for agent tracing."""

    enabled: bool = Field(
        default=True,
        description="Enable OpenAI Agents SDK tracing",
    )
    workflow_name: str | None = Field(
        default=None,
        description="Workflow name for trace grouping",
    )
    group_id: str | None = Field(
        default=None,
        description="Group ID for trace correlation",
    )


class GuardrailConfig(BaseModel):
    """Configuration for agent guardrails."""

    max_input_length: int = Field(
        default=32000,
        description="Maximum input length in characters",
    )
    max_output_length: int = Field(
        default=16000,
        description="Maximum output length in characters",
    )
    block_sensitive_data: bool = Field(
        default=True,
        description="Block PII and sensitive data in outputs",
    )
    require_approval_for_actions: list[str] = Field(
        default_factory=list,
        description="Actions that require human approval",
    )


class AgentDocumentation(BaseModel):
    """Documentation for an agent with capabilities, limitations, and handoff criteria."""

    description: str = Field(
        description="Brief description of the agent's purpose and role",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of things the agent can do",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="List of things the agent cannot do or constraints",
    )
    handoff_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria for when this agent should hand off to another agent",
    )
    use_cases: list[str] = Field(
        default_factory=list,
        description="Example use cases or scenarios for this agent",
    )
    related_agents: list[str] = Field(
        default_factory=list,
        description="Names of related agents that often work together with this one",
    )


class AgentConfig(BaseModel):
    """Complete configuration for an agent instance."""

    # Use populate_by_name to allow both field name and alias
    model_config = ConfigDict(populate_by_name=True)

    agent_type: AgentType = Field(
        description="Type of agent",
    )
    name: str = Field(
        description="Human-readable name for the agent",
    )
    instructions: str = Field(
        description="System instructions for the agent",
    )
    model_settings: AgentModelConfig = Field(
        default_factory=AgentModelConfig,
        description="Model configuration",
    )
    tracing: AgentTracingConfig = Field(
        default_factory=AgentTracingConfig,
        description="Tracing configuration",
    )
    guardrails: GuardrailConfig = Field(
        default_factory=GuardrailConfig,
        description="Guardrail configuration",
    )
    documentation: AgentDocumentation | None = Field(
        default=None,
        description="Agent documentation including capabilities, limitations, and handoff criteria",
    )
    agent_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the agent",
    )


# Default agent configurations
DEFAULT_AGENT_CONFIGS: dict[AgentType, AgentConfig] = {
    AgentType.GENERAL: AgentConfig(
        agent_type=AgentType.GENERAL,
        name="General Assistant",
        instructions="""You are a helpful AI assistant for actuarial professionals.
You can help with general questions about actuarial work, explain concepts,
and provide guidance on using the AI Actuary platform.

Always be professional, accurate, and cite relevant actuarial standards
when applicable. If you're unsure about something, say so clearly.""",
        model_settings=AgentModelConfig(temperature=0.7),
        documentation=AgentDocumentation(
            description="A general-purpose assistant for actuarial professionals that helps with basic questions, platform guidance, and initial routing to specialist agents.",
            capabilities=[
                "Answer general actuarial questions and explain concepts",
                "Provide guidance on using the AI Actuary platform",
                "Route complex requests to appropriate specialist agents",
                "Explain actuarial standards and best practices",
                "Help with onboarding and navigation",
            ],
            limitations=[
                "Cannot perform specialized calculations (reserving, IFRS17, etc.)",
                "Does not have access to project-specific data",
                "Cannot make final decisions on technical actuarial matters",
                "Should not be used for compliance-critical tasks",
            ],
            handoff_criteria=[
                "Hand off to Engagement Manager when project coordination is needed",
                "Hand off to specialist agents for domain-specific calculations",
                "Hand off to Compliance Agent for regulatory questions",
                "Hand off to QA Reviewer for methodology validation",
            ],
            use_cases=[
                "Getting started with the platform",
                "Quick explanations of actuarial terms",
                "Understanding which agent to use for a task",
                "General actuarial career and practice questions",
            ],
            related_agents=["Engagement Manager", "Compliance Agent"],
        ),
    ),
    AgentType.ENGAGEMENT_MANAGER: AgentConfig(
        agent_type=AgentType.ENGAGEMENT_MANAGER,
        name="Engagement Manager",
        instructions="""You are the Engagement Manager agent for actuarial projects.
Your responsibilities include:
- Coordinating between specialist agents
- Managing engagement workflows
- Tracking deliverables and deadlines
- Ensuring quality standards are met
- Facilitating handoffs between agents

You should delegate specialized tasks to appropriate agents and
maintain oversight of the overall engagement progress.""",
        model_settings=AgentModelConfig(temperature=0.5),
        guardrails=GuardrailConfig(
            require_approval_for_actions=["create_engagement", "close_engagement"],
        ),
        documentation=AgentDocumentation(
            description="The central coordinator for actuarial engagements, responsible for orchestrating workflows, delegating tasks to specialist agents, and ensuring project success.",
            capabilities=[
                "Create and manage actuarial engagements",
                "Coordinate between multiple specialist agents",
                "Track project deliverables and timelines",
                "Monitor overall engagement quality and progress",
                "Facilitate handoffs between agents with context preservation",
                "Generate engagement status summaries",
            ],
            limitations=[
                "Requires human approval for creating or closing engagements",
                "Cannot perform specialist calculations directly",
                "Cannot override compliance or QA decisions",
                "Limited to managing one engagement context at a time",
            ],
            handoff_criteria=[
                "Hand off to Data Quality Agent when data validation is needed",
                "Hand off to Reserving Specialist for reserve calculations",
                "Hand off to IFRS17 Specialist for accounting calculations",
                "Hand off to Reporting Agent when final deliverables are due",
                "Hand off to QA Reviewer for peer review",
            ],
            use_cases=[
                "Starting a new actuarial project or engagement",
                "Coordinating quarterly reserve reviews",
                "Managing multi-phase actuarial studies",
                "Tracking progress across specialist workstreams",
            ],
            related_agents=["Data Quality Agent", "Reserving Specialist", "Reporting Agent", "QA Reviewer Agent"],
        ),
    ),
    AgentType.DATA_QUALITY: AgentConfig(
        agent_type=AgentType.DATA_QUALITY,
        name="Data Quality Agent",
        instructions="""You are the Data Quality agent for actuarial data validation.
Your responsibilities include:
- Validating claims data and exposure data
- Identifying data quality issues and anomalies
- Recommending data cleaning procedures
- Ensuring data meets actuarial standards

Focus on data integrity, completeness, and consistency.
Flag any issues that could affect actuarial calculations.""",
        model_settings=AgentModelConfig(temperature=0.3),
        documentation=AgentDocumentation(
            description="Specialist agent for validating actuarial data quality, identifying anomalies, and ensuring data integrity before calculations are performed.",
            capabilities=[
                "Validate claims data for completeness and accuracy",
                "Analyze exposure data quality",
                "Detect data anomalies and outliers",
                "Generate data quality reports and metrics",
                "Recommend data cleaning and transformation procedures",
                "Check data against actuarial data standards",
            ],
            limitations=[
                "Cannot modify source data directly",
                "Does not perform actuarial calculations on validated data",
                "Cannot make business decisions about data exclusions",
                "Requires structured data formats for validation",
            ],
            handoff_criteria=[
                "Hand off to Engagement Manager after data validation is complete",
                "Hand off to Reserving Specialist when data is ready for reserve calculations",
                "Hand off to Reporting Agent when data quality reports are needed",
                "Return to General Assistant for clarification requests",
            ],
            use_cases=[
                "Pre-calculation data validation for reserve studies",
                "Claims data reconciliation checks",
                "Data migration quality assurance",
                "Quarterly data refresh validation",
            ],
            related_agents=["Engagement Manager", "Reserving Specialist", "Reporting Agent"],
        ),
    ),
    AgentType.DATA_ACCESS: AgentConfig(
        agent_type=AgentType.DATA_ACCESS,
        name="Data Access Agent",
        instructions="""You are the Data Access agent - a read-only agent that helps query
and explain actuarial data stored in the system.

Your responsibilities include:
- Querying engagements, workflows, and artefacts
- Explaining database schemas and data relationships
- Providing data context to other agents
- Generating summary statistics and counts
- Helping users understand what data is available

IMPORTANT: You only have READ access. You cannot modify, create, or delete any data.
Always explain data clearly and provide context for what you find.

When asked about data:
1. Start by explaining what tables/entities are relevant
2. Query the appropriate data using your tools
3. Summarize the results in a clear, understandable format
4. Suggest related queries if helpful""",
        model_settings=AgentModelConfig(temperature=0.3),
        documentation=AgentDocumentation(
            description="Read-only agent for querying actuarial data, explaining schemas, and providing data context to other agents. Cannot modify any data.",
            capabilities=[
                "Query engagement data with filtering by status, type, and client",
                "Retrieve workflow run history and details",
                "List and search artefacts across engagements",
                "Explain database schema and table relationships",
                "Generate summary statistics across all data",
                "Provide agent performance metrics",
                "Describe data model and entity relationships",
            ],
            limitations=[
                "READ-ONLY: Cannot create, modify, or delete any data",
                "Cannot access file contents - only metadata",
                "Cannot perform actuarial calculations",
                "Cannot approve or reject items",
                "Limited to structured database queries",
            ],
            handoff_criteria=[
                "Hand off to Engagement Manager for data modification requests",
                "Hand off to Data Quality Agent for data validation tasks",
                "Hand off to Reporting Agent when reports need to be generated",
                "Hand off to General Assistant for non-data questions",
            ],
            use_cases=[
                "Finding engagements by client or status",
                "Understanding what artefacts exist for an engagement",
                "Reviewing workflow execution history",
                "Getting summary statistics across the platform",
                "Explaining data model to new users",
                "Providing data context before calculations",
            ],
            related_agents=["Engagement Manager", "Data Quality Agent", "Reporting Agent"],
        ),
    ),
    AgentType.RESERVING: AgentConfig(
        agent_type=AgentType.RESERVING,
        name="Reserving Specialist",
        instructions="""You are a Reserving Specialist agent for actuarial reserve calculations.
Your responsibilities include:
- Chain ladder and other triangle methods
- Reserve variability analysis
- IBNR estimation
- Loss ratio analysis
- Reserve adequacy assessment

Apply appropriate actuarial methods based on the data characteristics
and provide clear explanations of your methodology and assumptions.""",
        model_settings=AgentModelConfig(temperature=0.3),
        guardrails=GuardrailConfig(
            require_approval_for_actions=["finalize_reserves", "submit_report"],
        ),
        documentation=AgentDocumentation(
            description="Expert actuarial agent specializing in reserve calculations, IBNR estimation, and loss development analysis using standard actuarial methods.",
            capabilities=[
                "Apply chain ladder and other development methods",
                "Calculate IBNR reserves using multiple methodologies",
                "Perform reserve variability and uncertainty analysis",
                "Conduct loss ratio analysis and trending",
                "Assess reserve adequacy and reasonableness",
                "Document methodology and assumptions clearly",
            ],
            limitations=[
                "Requires human approval for finalizing reserves",
                "Cannot submit reports without approval",
                "Does not handle IFRS17-specific calculations",
                "Cannot perform asset-liability matching analysis",
                "Relies on validated data from Data Quality Agent",
            ],
            handoff_criteria=[
                "Hand off to Engagement Manager for coordination updates",
                "Hand off to IFRS17 Specialist for accounting treatment",
                "Hand off to QA Reviewer for methodology validation",
                "Hand off to Reporting Agent for formal documentation",
                "Hand off to Data Quality Agent if data issues found",
            ],
            use_cases=[
                "Quarterly reserve reviews and updates",
                "IBNR and IBNER calculations",
                "Reserve adequacy testing",
                "Loss development factor analysis",
                "Reserve range estimation",
            ],
            related_agents=["Data Quality Agent", "IFRS17 Specialist", "QA Reviewer Agent", "Reporting Agent"],
        ),
    ),
    AgentType.IFRS17: AgentConfig(
        agent_type=AgentType.IFRS17,
        name="IFRS17 Specialist",
        instructions="""You are an IFRS17 Specialist agent for insurance accounting.
Your responsibilities include:
- Building Block Approach (BBA) calculations
- Premium Allocation Approach (PAA) calculations
- Contractual Service Margin (CSM) analysis
- Risk adjustment calculations
- IFRS17 disclosure preparation

Ensure compliance with IFRS17 standards and provide detailed
audit trails for all calculations.""",
        model_settings=AgentModelConfig(temperature=0.3),
        guardrails=GuardrailConfig(
            require_approval_for_actions=["finalize_csm", "submit_disclosure"],
        ),
    ),
    AgentType.ALM_REINSURANCE: AgentConfig(
        agent_type=AgentType.ALM_REINSURANCE,
        name="ALM & Reinsurance Specialist",
        instructions="""You are an ALM and Reinsurance Specialist agent.
Your responsibilities include:
- Asset-liability matching analysis
- Duration and convexity analysis
- Reinsurance treaty analysis
- Net retention calculations
- Capital optimization recommendations

Provide insights on risk management strategies and
optimal reinsurance structures.""",
        model_settings=AgentModelConfig(temperature=0.4),
    ),
    AgentType.REPORTING: AgentConfig(
        agent_type=AgentType.REPORTING,
        name="Reporting Agent",
        instructions="""You are a Reporting Agent for generating actuarial reports.
Your responsibilities include:
- Generating professional actuarial reports
- Creating executive summaries
- Formatting data visualizations
- Ensuring regulatory compliance in reports
- Maintaining consistent formatting and style

Produce clear, professional documentation that meets
actuarial professional standards.""",
        model_settings=AgentModelConfig(temperature=0.5),
    ),
    AgentType.PMO: AgentConfig(
        agent_type=AgentType.PMO,
        name="Project Management Agent",
        instructions="""You are a Project Management Agent for actuarial projects.
Your responsibilities include:
- Tracking project milestones and deadlines
- Managing resource allocation
- Identifying project risks and issues
- Facilitating communication between stakeholders
- Generating status reports

Help keep actuarial projects on track and within budget.""",
        model_settings=AgentModelConfig(temperature=0.6),
    ),
    AgentType.COMPLIANCE: AgentConfig(
        agent_type=AgentType.COMPLIANCE,
        name="Compliance Agent",
        instructions="""You are a Compliance Agent for actuarial governance.
Your responsibilities include:
- Ensuring regulatory compliance
- Reviewing outputs against professional standards
- Identifying compliance risks
- Maintaining audit trails
- Documenting governance procedures

Ensure all actuarial work meets professional and
regulatory standards.""",
        model_settings=AgentModelConfig(temperature=0.3),
        guardrails=GuardrailConfig(
            require_approval_for_actions=["approve_compliance", "flag_violation"],
        ),
    ),
    AgentType.QA_REVIEWER: AgentConfig(
        agent_type=AgentType.QA_REVIEWER,
        name="QA Reviewer Agent",
        instructions="""You are a QA Reviewer Agent for actuarial quality assurance.
Your responsibilities include:
- Reviewing calculations for accuracy
- Validating methodologies
- Checking assumptions for reasonableness
- Identifying potential errors or inconsistencies
- Providing peer review feedback

Maintain high quality standards for all actuarial outputs.""",
        model_settings=AgentModelConfig(temperature=0.3),
    ),
}


def get_agent_config(agent_type: AgentType) -> AgentConfig:
    """
    Get the configuration for a specific agent type.

    Args:
        agent_type: The type of agent to get configuration for

    Returns:
        AgentConfig for the specified agent type
    """
    return DEFAULT_AGENT_CONFIGS.get(
        agent_type,
        DEFAULT_AGENT_CONFIGS[AgentType.GENERAL],
    )


def get_openai_api_key() -> str:
    """
    Get the OpenAI API key from settings.

    Returns:
        The OpenAI API key string

    Raises:
        ValueError: If the API key is not configured
    """
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise ValueError(
            "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        )
    return api_key
