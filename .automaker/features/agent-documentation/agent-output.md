I'll review the previous exploration work and continue implementing the agent documentation feature. Let me first check what's already been discovered and then complete the implementation.

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/base.py"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/__init__.py"
}

Now I have a good understanding of the agent system. Let me also check the API routes for agents and the frontend structure:

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/api/routes/agents.py"
}

🔧 Tool: Bash
Input: {
  "command": "ls -la /Users/jared/Documents/FynbosAI/Products/my-ai-actuary/frontend/src/",
  "description": "List frontend src directory"
}

🔧 Tool: Bash
Input: {
  "command": "find /Users/jared/Documents/FynbosAI/Products/my-ai-actuary/frontend -name \"*.tsx\" -o -name \"*.ts\" | grep -iE \"(agent|doc)\" | head -20",
  "description": "Find agent-related frontend files"
}

Let me check the actual project structure to find the frontend:

🔧 Tool: Bash
Input: {
  "command": "ls -la /Users/jared/Documents/FynbosAI/Products/my-ai-actuary/",
  "description": "List project root directory"
}

🔧 Tool: Glob
Input: {
  "pattern": "**/src/**/*.{tsx,ts}",
  "path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary"
}

This is a Next.js project with frontend files at the root level (app, components, lib directories). Let me check the frontend structure and see what agent-related UI exists:

🔧 Tool: Glob
Input: {
  "pattern": "app/**/*.{tsx,ts}",
  "path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary"
}

🔧 Tool: Glob
Input: {
  "pattern": "components/**/*.{tsx,ts}",
  "path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary"
}

🔧 Tool: Bash
Input: {
  "command": "ls -la /Users/jared/Documents/FynbosAI/Products/my-ai-actuary/.automaker/",
  "description": "Check .automaker directory for docs"
}

Now I have a good understanding. This is a Next.js project with a Python FastAPI backend. The agents are defined in the backend/agent_definitions directory. Let me now check what features exist and understand the documentation structure:

🔧 Tool: TodoWrite
Input: {
  "todos": [
    {
      "content": "Create AgentDocumentation model in backend config",
      "status": "in_progress",
      "activeForm": "Creating AgentDocumentation model in backend config"
    },
    {
      "content": "Update agent configurations with documentation fields",
      "status": "pending",
      "activeForm": "Updating agent configurations with documentation fields"
    },
    {
      "content": "Create API endpoint to expose agent documentation",
      "status": "pending",
      "activeForm": "Creating API endpoint for agent documentation"
    },
    {
      "content": "Create frontend page to display agent documentation",
      "status": "pending",
      "activeForm": "Creating frontend page for agent documentation"
    },
    {
      "content": "Verify implementation with Playwright test",
      "status": "pending",
      "activeForm": "Verifying implementation with Playwright test"
    }
  ]
}

Now let me implement the agent documentation feature. I'll start by creating a documentation model and enhancing the agent configurations:

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py"
}

Now I'll add the AgentDocumentation model to the config file and update the configurations with comprehensive documentation:

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "class GuardrailConfig(BaseModel):\n    \"\"\"Configuration for agent guardrails.\"\"\"\n\n    max_input_length: int = Field(\n        default=32000,\n        description=\"Maximum input length in characters\",\n    )\n    max_output_length: int = Field(\n        default=16000,\n        description=\"Maximum output length in characters\",\n    )\n    block_sensitive_data: bool = Field(\n        default=True,\n        description=\"Block PII and sensitive data in outputs\",\n    )\n    require_approval_for_actions: list[str] = Field(\n        default_factory=list,\n        description=\"Actions that require human approval\",\n    )",
  "new_string": "class GuardrailConfig(BaseModel):\n    \"\"\"Configuration for agent guardrails.\"\"\"\n\n    max_input_length: int = Field(\n        default=32000,\n        description=\"Maximum input length in characters\",\n    )\n    max_output_length: int = Field(\n        default=16000,\n        description=\"Maximum output length in characters\",\n    )\n    block_sensitive_data: bool = Field(\n        default=True,\n        description=\"Block PII and sensitive data in outputs\",\n    )\n    require_approval_for_actions: list[str] = Field(\n        default_factory=list,\n        description=\"Actions that require human approval\",\n    )\n\n\nclass AgentDocumentation(BaseModel):\n    \"\"\"Documentation for an agent with capabilities, limitations, and handoff criteria.\"\"\"\n\n    description: str = Field(\n        description=\"Brief description of the agent's purpose and role\",\n    )\n    capabilities: list[str] = Field(\n        default_factory=list,\n        description=\"List of things the agent can do\",\n    )\n    limitations: list[str] = Field(\n        default_factory=list,\n        description=\"List of things the agent cannot do or constraints\",\n    )\n    handoff_criteria: list[str] = Field(\n        default_factory=list,\n        description=\"Criteria for when this agent should hand off to another agent\",\n    )\n    use_cases: list[str] = Field(\n        default_factory=list,\n        description=\"Example use cases or scenarios for this agent\",\n    )\n    related_agents: list[str] = Field(\n        default_factory=list,\n        description=\"Names of related agents that often work together with this one\",\n    )"
}

Now I need to add the documentation field to the AgentConfig model:

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "    guardrails: GuardrailConfig = Field(\n        default_factory=GuardrailConfig,\n        description=\"Guardrail configuration\",\n    )\n    agent_metadata: dict[str, Any] = Field(\n        default_factory=dict,\n        description=\"Additional metadata for the agent\",\n    )",
  "new_string": "    guardrails: GuardrailConfig = Field(\n        default_factory=GuardrailConfig,\n        description=\"Guardrail configuration\",\n    )\n    documentation: AgentDocumentation | None = Field(\n        default=None,\n        description=\"Agent documentation including capabilities, limitations, and handoff criteria\",\n    )\n    agent_metadata: dict[str, Any] = Field(\n        default_factory=dict,\n        description=\"Additional metadata for the agent\",\n    )"
}

Now I need to update the DEFAULT_AGENT_CONFIGS with documentation for each agent. Let me do this by replacing each agent configuration:

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "# Default agent configurations\nDEFAULT_AGENT_CONFIGS: dict[AgentType, AgentConfig] = {\n    AgentType.GENERAL: AgentConfig(\n        agent_type=AgentType.GENERAL,\n        name=\"General Assistant\",\n        instructions=\"\"\"You are a helpful AI assistant for actuarial professionals.\nYou can help with general questions about actuarial work, explain concepts,\nand provide guidance on using the AI Actuary platform.\n\nAlways be professional, accurate, and cite relevant actuarial standards\nwhen applicable. If you're unsure about something, say so clearly.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.7),\n    ),",
  "new_string": "# Default agent configurations\nDEFAULT_AGENT_CONFIGS: dict[AgentType, AgentConfig] = {\n    AgentType.GENERAL: AgentConfig(\n        agent_type=AgentType.GENERAL,\n        name=\"General Assistant\",\n        instructions=\"\"\"You are a helpful AI assistant for actuarial professionals.\nYou can help with general questions about actuarial work, explain concepts,\nand provide guidance on using the AI Actuary platform.\n\nAlways be professional, accurate, and cite relevant actuarial standards\nwhen applicable. If you're unsure about something, say so clearly.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.7),\n        documentation=AgentDocumentation(\n            description=\"A general-purpose assistant for actuarial professionals that helps with basic questions, platform guidance, and initial routing to specialist agents.\",\n            capabilities=[\n                \"Answer general actuarial questions and explain concepts\",\n                \"Provide guidance on using the AI Actuary platform\",\n                \"Route complex requests to appropriate specialist agents\",\n                \"Explain actuarial standards and best practices\",\n                \"Help with onboarding and navigation\",\n            ],\n            limitations=[\n                \"Cannot perform specialized calculations (reserving, IFRS17, etc.)\",\n                \"Does not have access to project-specific data\",\n                \"Cannot make final decisions on technical actuarial matters\",\n                \"Should not be used for compliance-critical tasks\",\n            ],\n            handoff_criteria=[\n                \"Hand off to Engagement Manager when project coordination is needed\",\n                \"Hand off to specialist agents for domain-specific calculations\",\n                \"Hand off to Compliance Agent for regulatory questions\",\n                \"Hand off to QA Reviewer for methodology validation\",\n            ],\n            use_cases=[\n                \"Getting started with the platform\",\n                \"Quick explanations of actuarial terms\",\n                \"Understanding which agent to use for a task\",\n                \"General actuarial career and practice questions\",\n            ],\n            related_agents=[\"Engagement Manager\", \"Compliance Agent\"],\n        ),\n    ),"
}

Now let me update the remaining agents with documentation:

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "    AgentType.ENGAGEMENT_MANAGER: AgentConfig(\n        agent_type=AgentType.ENGAGEMENT_MANAGER,\n        name=\"Engagement Manager\",\n        instructions=\"\"\"You are the Engagement Manager agent for actuarial projects.\nYour responsibilities include:\n- Coordinating between specialist agents\n- Managing engagement workflows\n- Tracking deliverables and deadlines\n- Ensuring quality standards are met\n- Facilitating handoffs between agents\n\nYou should delegate specialized tasks to appropriate agents and\nmaintain oversight of the overall engagement progress.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.5),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"create_engagement\", \"close_engagement\"],\n        ),\n    ),",
  "new_string": "    AgentType.ENGAGEMENT_MANAGER: AgentConfig(\n        agent_type=AgentType.ENGAGEMENT_MANAGER,\n        name=\"Engagement Manager\",\n        instructions=\"\"\"You are the Engagement Manager agent for actuarial projects.\nYour responsibilities include:\n- Coordinating between specialist agents\n- Managing engagement workflows\n- Tracking deliverables and deadlines\n- Ensuring quality standards are met\n- Facilitating handoffs between agents\n\nYou should delegate specialized tasks to appropriate agents and\nmaintain oversight of the overall engagement progress.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.5),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"create_engagement\", \"close_engagement\"],\n        ),\n        documentation=AgentDocumentation(\n            description=\"The central coordinator for actuarial engagements, responsible for orchestrating workflows, delegating tasks to specialist agents, and ensuring project success.\",\n            capabilities=[\n                \"Create and manage actuarial engagements\",\n                \"Coordinate between multiple specialist agents\",\n                \"Track project deliverables and timelines\",\n                \"Monitor overall engagement quality and progress\",\n                \"Facilitate handoffs between agents with context preservation\",\n                \"Generate engagement status summaries\",\n            ],\n            limitations=[\n                \"Requires human approval for creating or closing engagements\",\n                \"Cannot perform specialist calculations directly\",\n                \"Cannot override compliance or QA decisions\",\n                \"Limited to managing one engagement context at a time\",\n            ],\n            handoff_criteria=[\n                \"Hand off to Data Quality Agent when data validation is needed\",\n                \"Hand off to Reserving Specialist for reserve calculations\",\n                \"Hand off to IFRS17 Specialist for accounting calculations\",\n                \"Hand off to Reporting Agent when final deliverables are due\",\n                \"Hand off to QA Reviewer for peer review\",\n            ],\n            use_cases=[\n                \"Starting a new actuarial project or engagement\",\n                \"Coordinating quarterly reserve reviews\",\n                \"Managing multi-phase actuarial studies\",\n                \"Tracking progress across specialist workstreams\",\n            ],\n            related_agents=[\"Data Quality Agent\", \"Reserving Specialist\", \"Reporting Agent\", \"QA Reviewer Agent\"],\n        ),\n    ),"
}

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "    AgentType.DATA_QUALITY: AgentConfig(\n        agent_type=AgentType.DATA_QUALITY,\n        name=\"Data Quality Agent\",\n        instructions=\"\"\"You are the Data Quality agent for actuarial data validation.\nYour responsibilities include:\n- Validating claims data and exposure data\n- Identifying data quality issues and anomalies\n- Recommending data cleaning procedures\n- Ensuring data meets actuarial standards\n\nFocus on data integrity, completeness, and consistency.\nFlag any issues that could affect actuarial calculations.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n    ),",
  "new_string": "    AgentType.DATA_QUALITY: AgentConfig(\n        agent_type=AgentType.DATA_QUALITY,\n        name=\"Data Quality Agent\",\n        instructions=\"\"\"You are the Data Quality agent for actuarial data validation.\nYour responsibilities include:\n- Validating claims data and exposure data\n- Identifying data quality issues and anomalies\n- Recommending data cleaning procedures\n- Ensuring data meets actuarial standards\n\nFocus on data integrity, completeness, and consistency.\nFlag any issues that could affect actuarial calculations.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n        documentation=AgentDocumentation(\n            description=\"Specialist agent for validating actuarial data quality, identifying anomalies, and ensuring data integrity before calculations are performed.\",\n            capabilities=[\n                \"Validate claims data for completeness and accuracy\",\n                \"Analyze exposure data quality\",\n                \"Detect data anomalies and outliers\",\n                \"Generate data quality reports and metrics\",\n                \"Recommend data cleaning and transformation procedures\",\n                \"Check data against actuarial data standards\",\n            ],\n            limitations=[\n                \"Cannot modify source data directly\",\n                \"Does not perform actuarial calculations on validated data\",\n                \"Cannot make business decisions about data exclusions\",\n                \"Requires structured data formats for validation\",\n            ],\n            handoff_criteria=[\n                \"Hand off to Engagement Manager after data validation is complete\",\n                \"Hand off to Reserving Specialist when data is ready for reserve calculations\",\n                \"Hand off to Reporting Agent when data quality reports are needed\",\n                \"Return to General Assistant for clarification requests\",\n            ],\n            use_cases=[\n                \"Pre-calculation data validation for reserve studies\",\n                \"Claims data reconciliation checks\",\n                \"Data migration quality assurance\",\n                \"Quarterly data refresh validation\",\n            ],\n            related_agents=[\"Engagement Manager\", \"Reserving Specialist\", \"Reporting Agent\"],\n        ),\n    ),"
}

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "    AgentType.RESERVING: AgentConfig(\n        agent_type=AgentType.RESERVING,\n        name=\"Reserving Specialist\",\n        instructions=\"\"\"You are a Reserving Specialist agent for actuarial reserve calculations.\nYour responsibilities include:\n- Chain ladder and other triangle methods\n- Reserve variability analysis\n- IBNR estimation\n- Loss ratio analysis\n- Reserve adequacy assessment\n\nApply appropriate actuarial methods based on the data characteristics\nand provide clear explanations of your methodology and assumptions.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"finalize_reserves\", \"submit_report\"],\n        ),\n    ),",
  "new_string": "    AgentType.RESERVING: AgentConfig(\n        agent_type=AgentType.RESERVING,\n        name=\"Reserving Specialist\",\n        instructions=\"\"\"You are a Reserving Specialist agent for actuarial reserve calculations.\nYour responsibilities include:\n- Chain ladder and other triangle methods\n- Reserve variability analysis\n- IBNR estimation\n- Loss ratio analysis\n- Reserve adequacy assessment\n\nApply appropriate actuarial methods based on the data characteristics\nand provide clear explanations of your methodology and assumptions.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"finalize_reserves\", \"submit_report\"],\n        ),\n        documentation=AgentDocumentation(\n            description=\"Expert actuarial agent specializing in reserve calculations, IBNR estimation, and loss development analysis using standard actuarial methods.\",\n            capabilities=[\n                \"Apply chain ladder and other development methods\",\n                \"Calculate IBNR reserves using multiple methodologies\",\n                \"Perform reserve variability and uncertainty analysis\",\n                \"Conduct loss ratio analysis and trending\",\n                \"Assess reserve adequacy and reasonableness\",\n                \"Document methodology and assumptions clearly\",\n            ],\n            limitations=[\n                \"Requires human approval for finalizing reserves\",\n                \"Cannot submit reports without approval\",\n                \"Does not handle IFRS17-specific calculations\",\n                \"Cannot perform asset-liability matching analysis\",\n                \"Relies on validated data from Data Quality Agent\",\n            ],\n            handoff_criteria=[\n                \"Hand off to Engagement Manager for coordination updates\",\n                \"Hand off to IFRS17 Specialist for accounting treatment\",\n                \"Hand off to QA Reviewer for methodology validation\",\n                \"Hand off to Reporting Agent for formal documentation\",\n                \"Hand off to Data Quality Agent if data issues found\",\n            ],\n            use_cases=[\n                \"Quarterly reserve reviews and updates\",\n                \"IBNR and IBNER calculations\",\n                \"Reserve adequacy testing\",\n                \"Loss development factor analysis\",\n                \"Reserve range estimation\",\n            ],\n            related_agents=[\"Data Quality Agent\", \"IFRS17 Specialist\", \"QA Reviewer Agent\", \"Reporting Agent\"],\n        ),\n    ),"
}

🔧 Tool: Edit
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py",
  "old_string": "    AgentType.IFRS17: AgentConfig(\n        agent_type=AgentType.IFRS17,\n        name=\"IFRS17 Specialist\",\n        instructions=\"\"\"You are an IFRS17 Specialist agent for insurance accounting.\nYour responsibilities include:\n- Building Block Approach (BBA) calculations\n- Premium Allocation Approach (PAA) calculations\n- Contractual Service Margin (CSM) analysis\n- Risk adjustment calculations\n- IFRS17 disclosure preparation\n\nEnsure compliance with IFRS17 standards and provide detailed\naudit trails for all calculations.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"finalize_csm\", \"submit_disclosure\"],\n        ),\n    ),",
  "new_string": "    AgentType.IFRS17: AgentConfig(\n        agent_type=AgentType.IFRS17,\n        name=\"IFRS17 Specialist\",\n        instructions=\"\"\"You are an IFRS17 Specialist agent for insurance accounting.\nYour responsibilities include:\n- Building Block Approach (BBA) calculations\n- Premium Allocation Approach (PAA) calculations\n- Contractual Service Margin (CSM) analysis\n- Risk adjustment calculations\n- IFRS17 disclosure preparation\n\nEnsure compliance with IFRS17 standards and provide detailed\naudit trails for all calculations.\"\"\",\n        model_settings=AgentModelConfig(temperature=0.3),\n        guardrails=GuardrailConfig(\n            require_approval_for_actions=[\"finalize_csm\", \"submit_disclosure\"],\n        ),\n        documentation=AgentDocumentation(\n            description=\"Specialist agent for IFRS17 insurance accounting standard compliance, including BBA/PAA calculations, CSM analysis, and disclosure preparation.\",\n            capabilities=[\n                \"Perform Building Block Approach (BBA) calculations\",\n                \"Apply Premium Allocation Approach (PAA) where eligible\",\n                \"Calculate and track Contractual Service Margin (CSM)\",\n                \"Compute risk adjustments for non-financial risk\",\n                \"Prepare IFRS17 disclosure templates\",\n                \"Maintain detailed audit trails for all calculations\",\n            ],\n            limitations=[\n                \"Requires human approval for CSM finalization\",\n                \"Cannot submit disclosures without approval\",\n                \"Does not handle statutory/local GAAP reporting\",\n                \"Cannot make judgments on contract boundaries\",\n                \"Requires reserve inputs from Reserving Specialist\",\n            ],\n            handoff_criteria=[\n                \"Hand off to Engagement Manager for project coordination\",\n                \"Hand off to Reserving Specialist for underlying reserve calculations\",\n                \"Hand off to QA Reviewer for methodology review\",\n                \"Hand off to Reporting Agent for disclosure formatting\",\n                \"Hand off to Compliance Agent for regulatory alignment\",\n            ],\n            use_cases=[\n                \"IFRS17 transition calculations\",\n                \"Quarterly CSM roll-forward\",\n                \"PAA eligibility assessments\",\n                \"Risk adjustment computation\",\n                \"IFRS17 disclosure preparation\",\n            ],\n            related_agents=[\"Reserving Specialist\", \"QA Reviewer Agent\", \"Reporting Agent\", \"Compliance Agent\"],\n        ),\n    ),"
}

The file was modified by a linter or another process. Let me re-read the file and continue:

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/backend/agent_definitions/config.py"
}

I see a new DATA_ACCESS agent type was added. Let me continue adding documentation for the remaining agents. I'll add documentation for IFRS17, ALM_REINSURANCE, REPORTING, PMO, COMPLIANCE, and QA_REVIEWER: