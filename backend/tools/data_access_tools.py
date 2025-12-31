"""
Read-only data access tools for querying actuarial data.

Provides agents with the ability to query database schemas, retrieve
engagement data, workflow information, and artefacts without modifying
any data. All queries are read-only for safety.
"""

from typing import Any
from uuid import UUID

from agents import function_tool
from sqlalchemy import select, func, inspect, text
from sqlalchemy.orm import selectinload

from core.database import get_db_context
from core.logging import get_logger
from models import (
    Engagement,
    EngagementStatus,
    EngagementType,
    WorkflowRun,
    WorkflowStatus,
    WorkflowType,
    Artefact,
    ArtefactStatus,
    ArtefactType,
    Project,
    ProjectStatus,
    Session,
    ChatMessage,
    AgentMetric,
    AggregatedMetrics,
)

logger = get_logger(__name__)


# ============================================================================
# Schema Introspection Tools
# ============================================================================


@function_tool
async def get_database_schema() -> dict[str, Any]:
    """
    Get the complete database schema with all tables and their columns.

    Returns a dictionary describing all tables, their columns, types,
    and relationships. Useful for understanding the data model.

    Returns:
        Dictionary with table names as keys and column definitions as values.
    """
    async with get_db_context() as db:
        # Use SQLAlchemy inspection to get schema info
        result = await db.execute(text("""
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """))
        rows = result.fetchall()

        schema: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            table_name = row[0]
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append({
                "column_name": row[1],
                "data_type": row[2],
                "is_nullable": row[3] == "YES",
                "default": row[4],
            })

        logger.info("Schema retrieved", table_count=len(schema))
        return {
            "tables": schema,
            "table_count": len(schema),
        }


@function_tool
async def get_table_schema(table_name: str) -> dict[str, Any]:
    """
    Get detailed schema information for a specific table.

    Args:
        table_name: Name of the table to inspect

    Returns:
        Dictionary with columns, constraints, and indexes for the table.
    """
    async with get_db_context() as db:
        # Get columns
        columns_result = await db.execute(text("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            ORDER BY ordinal_position
        """), {"table_name": table_name})
        columns = columns_result.fetchall()

        if not columns:
            return {"error": f"Table '{table_name}' not found"}

        # Get primary key
        pk_result = await db.execute(text("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            WHERE tc.table_schema = 'public'
                AND tc.table_name = :table_name
                AND tc.constraint_type = 'PRIMARY KEY'
        """), {"table_name": table_name})
        pk_columns = [row[0] for row in pk_result.fetchall()]

        # Get foreign keys
        fk_result = await db.execute(text("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_schema = 'public'
                AND tc.table_name = :table_name
                AND tc.constraint_type = 'FOREIGN KEY'
        """), {"table_name": table_name})
        foreign_keys = [
            {
                "column": row[0],
                "references_table": row[1],
                "references_column": row[2],
            }
            for row in fk_result.fetchall()
        ]

        logger.info("Table schema retrieved", table_name=table_name)
        return {
            "table_name": table_name,
            "columns": [
                {
                    "name": col[0],
                    "type": col[1],
                    "nullable": col[2] == "YES",
                    "default": col[3],
                    "max_length": col[4],
                    "is_primary_key": col[0] in pk_columns,
                }
                for col in columns
            ],
            "primary_key": pk_columns,
            "foreign_keys": foreign_keys,
        }


@function_tool
async def explain_schema_relationships() -> dict[str, Any]:
    """
    Explain the relationships between key tables in the actuarial database.

    Returns a human-readable explanation of how the main entities relate
    to each other, useful for understanding data flow and querying.

    Returns:
        Dictionary with entity descriptions and relationship explanations.
    """
    return {
        "entities": {
            "Engagement": {
                "description": "Top-level entity representing a client actuarial project",
                "key_fields": ["client_code", "client_name", "engagement_type", "status", "period_start", "period_end"],
                "statuses": [s.value for s in EngagementStatus],
                "types": [t.value for t in EngagementType],
            },
            "Project": {
                "description": "Sub-project within an engagement for organizing work",
                "key_fields": ["name", "status", "priority", "due_date"],
                "parent": "Engagement",
            },
            "WorkflowRun": {
                "description": "Execution record for an actuarial workflow/process",
                "key_fields": ["workflow_type", "status", "period", "agent_name", "started_at", "completed_at"],
                "parent": "Engagement",
                "statuses": [s.value for s in WorkflowStatus],
                "types": [t.value for t in WorkflowType],
            },
            "Artefact": {
                "description": "Output file or document generated by a workflow",
                "key_fields": ["artefact_type", "name", "status", "file_name", "storage_path"],
                "parent": "Engagement (and optionally WorkflowRun)",
                "statuses": [s.value for s in ArtefactStatus],
                "types": [t.value for t in ArtefactType],
            },
            "Session": {
                "description": "Chat session for agent conversations",
                "key_fields": ["title", "agent_type", "is_active"],
                "parent": "Engagement (optional)",
            },
        },
        "relationships": [
            "Engagement -> has many -> Projects",
            "Engagement -> has many -> WorkflowRuns",
            "Engagement -> has many -> Artefacts",
            "Engagement -> has many -> Sessions",
            "WorkflowRun -> produces many -> Artefacts",
            "Session -> contains many -> ChatMessages",
        ],
        "common_queries": [
            "List all active engagements with their workflow status",
            "Find artefacts pending approval for a specific engagement",
            "Get workflow run history for a given period",
            "Count artefacts by type across all engagements",
        ],
    }


# ============================================================================
# Engagement Query Tools
# ============================================================================


@function_tool
async def list_engagements(
    status: str | None = None,
    engagement_type: str | None = None,
    client_code: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List engagements with optional filtering.

    Args:
        status: Filter by engagement status (draft, active, completed, etc.)
        engagement_type: Filter by type (reserving, ifrs17, alm, etc.)
        client_code: Filter by client code
        limit: Maximum number of results (default 50, max 100)

    Returns:
        Dictionary with list of engagements and count.
    """
    limit = min(limit, 100)  # Cap at 100

    async with get_db_context() as db:
        query = select(Engagement).where(Engagement.deleted_at.is_(None))

        if status:
            try:
                status_enum = EngagementStatus(status)
                query = query.where(Engagement.status == status_enum)
            except ValueError:
                return {"error": f"Invalid status: {status}. Valid values: {[s.value for s in EngagementStatus]}"}

        if engagement_type:
            try:
                type_enum = EngagementType(engagement_type)
                query = query.where(Engagement.engagement_type == type_enum)
            except ValueError:
                return {"error": f"Invalid type: {engagement_type}. Valid values: {[t.value for t in EngagementType]}"}

        if client_code:
            query = query.where(Engagement.client_code == client_code)

        query = query.order_by(Engagement.created_at.desc()).limit(limit)

        result = await db.execute(query)
        engagements = result.scalars().all()

        logger.info("Engagements listed", count=len(engagements))
        return {
            "engagements": [
                {
                    "id": str(e.id),
                    "client_code": e.client_code,
                    "client_name": e.client_name,
                    "name": e.name,
                    "engagement_type": e.engagement_type.value,
                    "status": e.status.value,
                    "period_start": e.period_start.isoformat() if e.period_start else None,
                    "period_end": e.period_end.isoformat() if e.period_end else None,
                    "due_date": e.due_date.isoformat() if e.due_date else None,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in engagements
            ],
            "count": len(engagements),
            "limit": limit,
        }


@function_tool
async def get_engagement_details(engagement_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific engagement.

    Args:
        engagement_id: UUID of the engagement

    Returns:
        Dictionary with full engagement details including workflow and artefact counts.
    """
    try:
        eng_uuid = UUID(engagement_id)
    except ValueError:
        return {"error": f"Invalid UUID format: {engagement_id}"}

    async with get_db_context() as db:
        # Get engagement with counts
        query = (
            select(Engagement)
            .where(Engagement.id == eng_uuid)
            .where(Engagement.deleted_at.is_(None))
        )
        result = await db.execute(query)
        engagement = result.scalar_one_or_none()

        if not engagement:
            return {"error": f"Engagement not found: {engagement_id}"}

        # Get workflow counts by status
        workflow_counts_result = await db.execute(
            select(WorkflowRun.status, func.count(WorkflowRun.id))
            .where(WorkflowRun.engagement_id == eng_uuid)
            .where(WorkflowRun.deleted_at.is_(None))
            .group_by(WorkflowRun.status)
        )
        workflow_counts = {row[0].value: row[1] for row in workflow_counts_result.fetchall()}

        # Get artefact counts by status
        artefact_counts_result = await db.execute(
            select(Artefact.status, func.count(Artefact.id))
            .where(Artefact.engagement_id == eng_uuid)
            .where(Artefact.deleted_at.is_(None))
            .group_by(Artefact.status)
        )
        artefact_counts = {row[0].value: row[1] for row in artefact_counts_result.fetchall()}

        logger.info("Engagement details retrieved", engagement_id=engagement_id)
        return {
            "engagement": {
                "id": str(engagement.id),
                "client_code": engagement.client_code,
                "client_name": engagement.client_name,
                "name": engagement.name,
                "description": engagement.description,
                "engagement_type": engagement.engagement_type.value,
                "status": engagement.status.value,
                "period_start": engagement.period_start.isoformat() if engagement.period_start else None,
                "period_end": engagement.period_end.isoformat() if engagement.period_end else None,
                "due_date": engagement.due_date.isoformat() if engagement.due_date else None,
                "lead_actuary_id": str(engagement.lead_actuary_id) if engagement.lead_actuary_id else None,
                "reviewer_id": str(engagement.reviewer_id) if engagement.reviewer_id else None,
                "config": engagement.config,
                "metadata": engagement.extra_metadata,
                "created_at": engagement.created_at.isoformat() if engagement.created_at else None,
                "updated_at": engagement.updated_at.isoformat() if engagement.updated_at else None,
            },
            "workflow_counts_by_status": workflow_counts,
            "artefact_counts_by_status": artefact_counts,
        }


@function_tool
async def get_engagement_summary_stats() -> dict[str, Any]:
    """
    Get summary statistics across all engagements.

    Returns aggregate counts of engagements by status and type,
    plus workflow and artefact totals.

    Returns:
        Dictionary with summary statistics.
    """
    async with get_db_context() as db:
        # Engagement counts by status
        eng_by_status_result = await db.execute(
            select(Engagement.status, func.count(Engagement.id))
            .where(Engagement.deleted_at.is_(None))
            .group_by(Engagement.status)
        )
        engagements_by_status = {row[0].value: row[1] for row in eng_by_status_result.fetchall()}

        # Engagement counts by type
        eng_by_type_result = await db.execute(
            select(Engagement.engagement_type, func.count(Engagement.id))
            .where(Engagement.deleted_at.is_(None))
            .group_by(Engagement.engagement_type)
        )
        engagements_by_type = {row[0].value: row[1] for row in eng_by_type_result.fetchall()}

        # Total workflows by status
        wf_by_status_result = await db.execute(
            select(WorkflowRun.status, func.count(WorkflowRun.id))
            .where(WorkflowRun.deleted_at.is_(None))
            .group_by(WorkflowRun.status)
        )
        workflows_by_status = {row[0].value: row[1] for row in wf_by_status_result.fetchall()}

        # Total artefacts by type
        art_by_type_result = await db.execute(
            select(Artefact.artefact_type, func.count(Artefact.id))
            .where(Artefact.deleted_at.is_(None))
            .group_by(Artefact.artefact_type)
        )
        artefacts_by_type = {row[0].value: row[1] for row in art_by_type_result.fetchall()}

        logger.info("Summary stats retrieved")
        return {
            "engagements": {
                "total": sum(engagements_by_status.values()),
                "by_status": engagements_by_status,
                "by_type": engagements_by_type,
            },
            "workflows": {
                "total": sum(workflows_by_status.values()),
                "by_status": workflows_by_status,
            },
            "artefacts": {
                "total": sum(artefacts_by_type.values()),
                "by_type": artefacts_by_type,
            },
        }


# ============================================================================
# Workflow Query Tools
# ============================================================================


@function_tool
async def list_workflow_runs(
    engagement_id: str | None = None,
    workflow_type: str | None = None,
    status: str | None = None,
    period: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List workflow runs with optional filtering.

    Args:
        engagement_id: Filter by engagement UUID
        workflow_type: Filter by workflow type
        status: Filter by status (pending, running, completed, failed, etc.)
        period: Filter by reporting period (e.g., "2024-Q4")
        limit: Maximum number of results (default 50, max 100)

    Returns:
        Dictionary with list of workflow runs and count.
    """
    limit = min(limit, 100)

    async with get_db_context() as db:
        query = select(WorkflowRun).where(WorkflowRun.deleted_at.is_(None))

        if engagement_id:
            try:
                eng_uuid = UUID(engagement_id)
                query = query.where(WorkflowRun.engagement_id == eng_uuid)
            except ValueError:
                return {"error": f"Invalid engagement_id UUID: {engagement_id}"}

        if workflow_type:
            try:
                wf_type = WorkflowType(workflow_type)
                query = query.where(WorkflowRun.workflow_type == wf_type)
            except ValueError:
                return {"error": f"Invalid workflow_type: {workflow_type}. Valid values: {[t.value for t in WorkflowType]}"}

        if status:
            try:
                status_enum = WorkflowStatus(status)
                query = query.where(WorkflowRun.status == status_enum)
            except ValueError:
                return {"error": f"Invalid status: {status}. Valid values: {[s.value for s in WorkflowStatus]}"}

        if period:
            query = query.where(WorkflowRun.period == period)

        query = query.order_by(WorkflowRun.created_at.desc()).limit(limit)

        result = await db.execute(query)
        workflows = result.scalars().all()

        logger.info("Workflow runs listed", count=len(workflows))
        return {
            "workflow_runs": [
                {
                    "id": str(wf.id),
                    "engagement_id": str(wf.engagement_id),
                    "workflow_type": wf.workflow_type.value,
                    "name": wf.name,
                    "status": wf.status.value,
                    "period": wf.period,
                    "agent_name": wf.agent_name,
                    "progress_percent": wf.progress_percent,
                    "started_at": wf.started_at.isoformat() if wf.started_at else None,
                    "completed_at": wf.completed_at.isoformat() if wf.completed_at else None,
                    "duration_seconds": wf.duration_seconds,
                    "error_message": wf.error_message,
                    "created_at": wf.created_at.isoformat() if wf.created_at else None,
                }
                for wf in workflows
            ],
            "count": len(workflows),
            "limit": limit,
        }


@function_tool
async def get_workflow_details(workflow_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific workflow run.

    Args:
        workflow_id: UUID of the workflow run

    Returns:
        Dictionary with full workflow details including input/output params and artefacts.
    """
    try:
        wf_uuid = UUID(workflow_id)
    except ValueError:
        return {"error": f"Invalid UUID format: {workflow_id}"}

    async with get_db_context() as db:
        query = (
            select(WorkflowRun)
            .where(WorkflowRun.id == wf_uuid)
            .where(WorkflowRun.deleted_at.is_(None))
        )
        result = await db.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            return {"error": f"Workflow run not found: {workflow_id}"}

        # Get artefact count
        artefact_result = await db.execute(
            select(func.count(Artefact.id))
            .where(Artefact.workflow_run_id == wf_uuid)
            .where(Artefact.deleted_at.is_(None))
        )
        artefact_count = artefact_result.scalar() or 0

        logger.info("Workflow details retrieved", workflow_id=workflow_id)
        return {
            "workflow_run": {
                "id": str(workflow.id),
                "engagement_id": str(workflow.engagement_id),
                "workflow_type": workflow.workflow_type.value,
                "name": workflow.name,
                "description": workflow.description,
                "status": workflow.status.value,
                "period": workflow.period,
                "agent_name": workflow.agent_name,
                "step_count": workflow.step_count,
                "current_step": workflow.current_step,
                "progress_percent": workflow.progress_percent,
                "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
                "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
                "duration_seconds": workflow.duration_seconds,
                "input_params": workflow.input_params,
                "output_summary": workflow.output_summary,
                "error_message": workflow.error_message,
                "error_details": workflow.error_details,
                "metrics": workflow.metrics,
                "trace_id": workflow.trace_id,
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
                "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            },
            "artefact_count": artefact_count,
        }


# ============================================================================
# Artefact Query Tools
# ============================================================================


@function_tool
async def list_artefacts(
    engagement_id: str | None = None,
    workflow_run_id: str | None = None,
    artefact_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List artefacts with optional filtering.

    Args:
        engagement_id: Filter by engagement UUID
        workflow_run_id: Filter by workflow run UUID
        artefact_type: Filter by artefact type (report, csv, excel, etc.)
        status: Filter by status (draft, pending_review, approved, etc.)
        limit: Maximum number of results (default 50, max 100)

    Returns:
        Dictionary with list of artefacts and count.
    """
    limit = min(limit, 100)

    async with get_db_context() as db:
        query = select(Artefact).where(Artefact.deleted_at.is_(None))

        if engagement_id:
            try:
                eng_uuid = UUID(engagement_id)
                query = query.where(Artefact.engagement_id == eng_uuid)
            except ValueError:
                return {"error": f"Invalid engagement_id UUID: {engagement_id}"}

        if workflow_run_id:
            try:
                wf_uuid = UUID(workflow_run_id)
                query = query.where(Artefact.workflow_run_id == wf_uuid)
            except ValueError:
                return {"error": f"Invalid workflow_run_id UUID: {workflow_run_id}"}

        if artefact_type:
            try:
                art_type = ArtefactType(artefact_type)
                query = query.where(Artefact.artefact_type == art_type)
            except ValueError:
                return {"error": f"Invalid artefact_type: {artefact_type}. Valid values: {[t.value for t in ArtefactType]}"}

        if status:
            try:
                status_enum = ArtefactStatus(status)
                query = query.where(Artefact.status == status_enum)
            except ValueError:
                return {"error": f"Invalid status: {status}. Valid values: {[s.value for s in ArtefactStatus]}"}

        query = query.order_by(Artefact.created_at.desc()).limit(limit)

        result = await db.execute(query)
        artefacts = result.scalars().all()

        logger.info("Artefacts listed", count=len(artefacts))
        return {
            "artefacts": [
                {
                    "id": str(a.id),
                    "engagement_id": str(a.engagement_id),
                    "workflow_run_id": str(a.workflow_run_id) if a.workflow_run_id else None,
                    "artefact_type": a.artefact_type.value,
                    "name": a.name,
                    "status": a.status.value,
                    "file_name": a.file_name,
                    "mime_type": a.mime_type,
                    "file_size": a.file_size,
                    "version": a.version,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in artefacts
            ],
            "count": len(artefacts),
            "limit": limit,
        }


@function_tool
async def get_artefact_details(artefact_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific artefact.

    Args:
        artefact_id: UUID of the artefact

    Returns:
        Dictionary with full artefact details including storage info.
    """
    try:
        art_uuid = UUID(artefact_id)
    except ValueError:
        return {"error": f"Invalid UUID format: {artefact_id}"}

    async with get_db_context() as db:
        query = (
            select(Artefact)
            .where(Artefact.id == art_uuid)
            .where(Artefact.deleted_at.is_(None))
        )
        result = await db.execute(query)
        artefact = result.scalar_one_or_none()

        if not artefact:
            return {"error": f"Artefact not found: {artefact_id}"}

        logger.info("Artefact details retrieved", artefact_id=artefact_id)
        return {
            "artefact": {
                "id": str(artefact.id),
                "engagement_id": str(artefact.engagement_id),
                "workflow_run_id": str(artefact.workflow_run_id) if artefact.workflow_run_id else None,
                "artefact_type": artefact.artefact_type.value,
                "name": artefact.name,
                "description": artefact.description,
                "status": artefact.status.value,
                "file_name": artefact.file_name,
                "mime_type": artefact.mime_type,
                "file_size": artefact.file_size,
                "storage_path": artefact.storage_path,
                "storage_bucket": artefact.storage_bucket,
                "storage_url": artefact.storage_url,
                "content_hash": artefact.content_hash,
                "version": artefact.version,
                "previous_version_id": str(artefact.previous_version_id) if artefact.previous_version_id else None,
                "metadata": artefact.extra_metadata,
                "trace_id": artefact.trace_id,
                "created_at": artefact.created_at.isoformat() if artefact.created_at else None,
                "updated_at": artefact.updated_at.isoformat() if artefact.updated_at else None,
            },
        }


# ============================================================================
# Agent Metrics Query Tools
# ============================================================================


@function_tool
async def get_agent_performance_metrics(
    agent_type: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    Get agent performance metrics for recent activity.

    Args:
        agent_type: Filter by specific agent type (optional)
        days: Number of days to look back (default 7, max 30)

    Returns:
        Dictionary with agent performance statistics.
    """
    from datetime import datetime, timedelta, timezone

    days = min(days, 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with get_db_context() as db:
        query = (
            select(AgentMetric)
            .where(AgentMetric.recorded_at >= cutoff)
        )

        if agent_type:
            query = query.where(AgentMetric.agent_type == agent_type)

        query = query.order_by(AgentMetric.recorded_at.desc())

        result = await db.execute(query)
        metrics = result.scalars().all()

        # Aggregate by agent type
        by_agent: dict[str, dict[str, Any]] = {}
        for m in metrics:
            if m.agent_type not in by_agent:
                by_agent[m.agent_type] = {
                    "total_runs": 0,
                    "total_tokens": 0,
                    "total_duration_ms": 0,
                    "success_count": 0,
                    "error_count": 0,
                }

            by_agent[m.agent_type]["total_runs"] += 1
            by_agent[m.agent_type]["total_tokens"] += m.total_tokens or 0
            by_agent[m.agent_type]["total_duration_ms"] += m.duration_ms or 0
            if m.success:
                by_agent[m.agent_type]["success_count"] += 1
            else:
                by_agent[m.agent_type]["error_count"] += 1

        # Calculate averages
        for agent, stats in by_agent.items():
            if stats["total_runs"] > 0:
                stats["avg_tokens_per_run"] = stats["total_tokens"] / stats["total_runs"]
                stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_runs"]
                stats["success_rate"] = stats["success_count"] / stats["total_runs"]

        logger.info("Agent metrics retrieved", agent_count=len(by_agent), days=days)
        return {
            "period_days": days,
            "total_metrics": len(metrics),
            "by_agent_type": by_agent,
        }


# Export all data access tools
DATA_ACCESS_TOOLS = [
    # Schema tools
    get_database_schema,
    get_table_schema,
    explain_schema_relationships,
    # Engagement tools
    list_engagements,
    get_engagement_details,
    get_engagement_summary_stats,
    # Workflow tools
    list_workflow_runs,
    get_workflow_details,
    # Artefact tools
    list_artefacts,
    get_artefact_details,
    # Metrics tools
    get_agent_performance_metrics,
]
