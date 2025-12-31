"""
Function tools and MCP servers for agent capabilities.

This module contains:
- Function tool definitions for agents
- MCP server integrations
- External API wrappers
- Codex CLI integration tools
- Knowledge base search and retrieval tools
"""

from tools.base_tools import (
    BASE_TOOLS,
    calculate_change_percentage,
    create_table_markdown,
    format_currency,
    format_percentage,
    get_current_datetime,
    summarize_numbers,
    validate_uuid,
)
from tools.codex_tools import (
    CODEX_TOOLS,
    cancel_cli_task,
    execute_cli_task,
    get_batch_status,
    get_cli_task_result,
    get_cli_task_status,
    list_cli_tasks,
    submit_batch_tasks,
    submit_cli_task,
)
from tools.knowledge_base_tools import (
    KNOWLEDGE_BASE_TOOLS,
    find_similar_precedents,
    get_actuarial_method,
    get_precedent,
    get_template,
    list_methods_by_category,
    search_knowledge_base,
)
from tools.data_access_tools import (
    DATA_ACCESS_TOOLS,
    get_database_schema,
    get_table_schema,
    explain_schema_relationships,
    list_engagements,
    get_engagement_details,
    get_engagement_summary_stats,
    list_workflow_runs,
    get_workflow_details,
    list_artefacts,
    get_artefact_details,
    get_agent_performance_metrics,
)

__all__ = [
    # Base tools
    "BASE_TOOLS",
    "get_current_datetime",
    "format_currency",
    "format_percentage",
    "calculate_change_percentage",
    "validate_uuid",
    "summarize_numbers",
    "create_table_markdown",
    # Codex CLI tools
    "CODEX_TOOLS",
    "submit_cli_task",
    "execute_cli_task",
    "get_cli_task_status",
    "get_cli_task_result",
    "cancel_cli_task",
    "list_cli_tasks",
    "submit_batch_tasks",
    "get_batch_status",
    # Knowledge base tools
    "KNOWLEDGE_BASE_TOOLS",
    "search_knowledge_base",
    "get_actuarial_method",
    "get_template",
    "get_precedent",
    "list_methods_by_category",
    "find_similar_precedents",
]
