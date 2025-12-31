"""
Tracing API routes for trace querying and monitoring.

Provides endpoints for:
- Querying traces and spans
- Viewing trace collector statistics
- Accessing audit trails
- Correlation between traces and audit logs
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.trace_collector import get_trace_collector
from core.tracing import SpanKind, SpanStatus
from models.audit import AuditAction, AuditLog, AuditSeverity
from services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/tracing", tags=["Tracing"])


# Request/Response Models
class SpanInfo(BaseModel):
    """Information about a trace span."""

    name: str = Field(description="Span operation name")
    trace_id: str = Field(description="Trace identifier")
    span_id: str = Field(description="Span identifier")
    parent_span_id: Optional[str] = Field(default=None, description="Parent span ID")
    kind: str = Field(description="Span kind (server, client, internal)")
    status: str = Field(description="Span status (ok, error, unset)")
    start_time: str = Field(description="Span start timestamp")
    end_time: Optional[str] = Field(default=None, description="Span end timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Duration in milliseconds")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Span attributes")
    events: list[dict[str, Any]] = Field(default_factory=list, description="Span events")


class TraceSummary(BaseModel):
    """Summary information about a trace."""

    trace_id: str = Field(description="Trace identifier")
    root_span: Optional[str] = Field(default=None, description="Root span name")
    span_count: int = Field(description="Number of spans in trace")
    start_time: Optional[str] = Field(default=None, description="Trace start time")
    end_time: Optional[str] = Field(default=None, description="Trace end time")
    duration_ms: Optional[float] = Field(default=None, description="Total duration")
    status: str = Field(description="Overall trace status")
    has_errors: bool = Field(description="Whether trace contains errors")


class TraceDetails(BaseModel):
    """Detailed information about a trace."""

    trace_id: str = Field(description="Trace identifier")
    root_span: Optional[SpanInfo] = Field(default=None, description="Root span details")
    spans: list[SpanInfo] = Field(description="All spans in the trace")
    span_count: int = Field(description="Number of spans")
    start_time: Optional[str] = Field(default=None, description="Trace start time")
    end_time: Optional[str] = Field(default=None, description="Trace end time")
    total_duration_ms: Optional[float] = Field(default=None, description="Total duration")
    has_errors: bool = Field(description="Whether trace contains errors")


class TraceListResponse(BaseModel):
    """Response model for listing traces."""

    traces: list[TraceSummary] = Field(description="List of trace summaries")
    total: int = Field(description="Total number of traces returned")


class TraceStatistics(BaseModel):
    """Trace collector statistics."""

    total_spans: int = Field(description="Total spans in buffer")
    total_traces: int = Field(description="Total unique traces")
    buffer_capacity: int = Field(description="Maximum buffer capacity")
    buffer_usage_percent: float = Field(description="Buffer usage percentage")
    status_distribution: dict[str, int] = Field(description="Span status distribution")
    kind_distribution: dict[str, int] = Field(description="Span kind distribution")
    average_duration_ms: float = Field(description="Average span duration")


class AuditLogInfo(BaseModel):
    """Audit log entry information."""

    id: str = Field(description="Audit log ID")
    action: str = Field(description="Action type")
    severity: str = Field(description="Severity level")
    resource_type: str = Field(description="Resource type")
    resource_id: Optional[str] = Field(default=None, description="Resource ID")
    description: str = Field(description="Action description")
    user_id: Optional[str] = Field(default=None, description="User who performed action")
    trace_id: Optional[str] = Field(default=None, description="Associated trace ID")
    session_id: Optional[str] = Field(default=None, description="Associated session ID")
    created_at: str = Field(description="Timestamp of the event")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional metadata")


class AuditLogListResponse(BaseModel):
    """Response model for listing audit logs."""

    logs: list[AuditLogInfo] = Field(description="List of audit logs")
    total: int = Field(description="Number of logs returned")


def _audit_log_to_info(log: "AuditLog") -> AuditLogInfo:
    """Convert an AuditLog model to AuditLogInfo response model.

    DRY helper to avoid repeating conversion logic across endpoints.
    """
    return AuditLogInfo(
        id=str(log.id),
        action=log.action.value,
        severity=log.severity.value,
        resource_type=log.resource_type,
        resource_id=str(log.resource_id) if log.resource_id else None,
        description=log.description,
        user_id=str(log.user_id) if log.user_id else None,
        trace_id=log.trace_id,
        session_id=str(log.session_id) if log.session_id else None,
        created_at=log.created_at.isoformat(),
        metadata=log.extra_metadata,
    )


class AuditStatistics(BaseModel):
    """Audit log statistics."""

    from_date: str = Field(description="Start of date range")
    to_date: str = Field(description="End of date range")
    total_count: int = Field(description="Total event count")
    by_action: dict[str, int] = Field(description="Count by action type")
    by_severity: dict[str, int] = Field(description="Count by severity")


# Endpoints
@router.get(
    "/traces",
    response_model=TraceListResponse,
    summary="List recent traces",
    description="Get a list of recent traces with optional filtering.",
)
async def list_traces(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum traces to return"),
    kind: Optional[str] = Query(default=None, description="Filter by span kind"),
    status: Optional[str] = Query(default=None, description="Filter by span status"),
    min_duration_ms: Optional[float] = Query(default=None, ge=0, description="Minimum duration filter"),
) -> TraceListResponse:
    """List recent traces with filtering."""
    collector = get_trace_collector()

    # Parse filters with validation
    span_kind: Optional[SpanKind] = None
    span_status: Optional[SpanStatus] = None

    if kind:
        try:
            span_kind = SpanKind(kind)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid span kind '{kind}'. Valid values: {[k.value for k in SpanKind]}",
            )

    if status:
        try:
            span_status = SpanStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid span status '{status}'. Valid values: {[s.value for s in SpanStatus]}",
            )

    traces = collector.get_recent_traces(
        limit=limit,
        kind=span_kind,
        status=span_status,
        min_duration_ms=min_duration_ms,
    )

    return TraceListResponse(
        traces=[TraceSummary(**trace) for trace in traces],
        total=len(traces),
    )


@router.get(
    "/traces/{trace_id}",
    response_model=TraceDetails,
    summary="Get trace details",
    description="Get detailed information about a specific trace.",
)
async def get_trace(trace_id: str) -> TraceDetails:
    """Get detailed trace information."""
    collector = get_trace_collector()
    details = collector.get_trace_details(trace_id)

    if not details:
        raise HTTPException(
            status_code=404,
            detail=f"Trace {trace_id} not found",
        )

    # Convert spans to SpanInfo models
    spans = [SpanInfo(**span) for span in details.get("spans", [])]
    root_span = SpanInfo(**details["root_span"]) if details.get("root_span") else None

    return TraceDetails(
        trace_id=details["trace_id"],
        root_span=root_span,
        spans=spans,
        span_count=details["span_count"],
        start_time=details.get("start_time"),
        end_time=details.get("end_time"),
        total_duration_ms=details.get("total_duration_ms"),
        has_errors=details["has_errors"],
    )


@router.get(
    "/statistics",
    response_model=TraceStatistics,
    summary="Get trace collector statistics",
    description="Get statistics about the trace collector.",
)
async def get_trace_statistics() -> TraceStatistics:
    """Get trace collector statistics."""
    collector = get_trace_collector()
    stats = collector.get_statistics()
    return TraceStatistics(**stats)


@router.post(
    "/cleanup",
    summary="Clean up old traces",
    description="Remove old traces from the in-memory buffer.",
)
async def cleanup_traces(
    max_age_seconds: int = Query(default=3600, ge=60, le=86400, description="Maximum age in seconds"),
) -> dict[str, Any]:
    """Clean up old traces from memory."""
    collector = get_trace_collector()
    removed = collector.cleanup_old_traces(max_age_seconds)

    return {
        "status": "success",
        "removed_traces": removed,
        "message": f"Removed {removed} old traces",
    }


# Audit endpoints
@router.get(
    "/audit",
    response_model=AuditLogListResponse,
    summary="List audit logs",
    description="Get recent audit log entries.",
)
async def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum logs to return"),
    severity: Optional[str] = Query(default=None, description="Filter by severity"),
    action: Optional[str] = Query(default=None, description="Filter by action type"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List recent audit logs."""
    service = AuditService(db)

    # Parse filters with validation
    audit_severity: Optional[AuditSeverity] = None
    audit_action: Optional[AuditAction] = None

    if severity:
        try:
            audit_severity = AuditSeverity(severity)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity '{severity}'. Valid values: {[s.value for s in AuditSeverity]}",
            )

    if action:
        try:
            audit_action = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action '{action}'. Valid values: {[a.value for a in AuditAction]}",
            )

    logs = await service.get_recent(
        limit=limit,
        severity=audit_severity,
        action=audit_action,
    )

    return AuditLogListResponse(
        logs=[_audit_log_to_info(log) for log in logs],
        total=len(logs),
    )


@router.get(
    "/audit/trace/{trace_id}",
    response_model=AuditLogListResponse,
    summary="Get audit logs by trace",
    description="Get all audit logs associated with a trace ID.",
)
async def get_audit_logs_by_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit logs for a specific trace."""
    service = AuditService(db)
    logs = await service.get_by_trace_id(trace_id)

    return AuditLogListResponse(
        logs=[_audit_log_to_info(log) for log in logs],
        total=len(logs),
    )


@router.get(
    "/audit/user/{user_id}",
    response_model=AuditLogListResponse,
    summary="Get audit logs by user",
    description="Get audit logs for a specific user.",
)
async def get_audit_logs_by_user(
    user_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit logs for a specific user."""
    service = AuditService(db)

    # Validate action filter
    audit_action: Optional[AuditAction] = None
    if action:
        try:
            audit_action = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action '{action}'. Valid values: {[a.value for a in AuditAction]}",
            )

    logs = await service.get_by_user(
        user_id=user_id,
        limit=limit,
        offset=offset,
        action=audit_action,
    )

    return AuditLogListResponse(
        logs=[_audit_log_to_info(log) for log in logs],
        total=len(logs),
    )


@router.get(
    "/audit/statistics",
    response_model=AuditStatistics,
    summary="Get audit statistics",
    description="Get statistics about audit log entries.",
)
async def get_audit_statistics(
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
) -> AuditStatistics:
    """Get audit log statistics."""
    service = AuditService(db)
    stats = await service.get_statistics(from_date=from_date, to_date=to_date)
    return AuditStatistics(**stats)


@router.get(
    "/audit/session/{session_id}",
    response_model=AuditLogListResponse,
    summary="Get session audit trail",
    description="Get the complete audit trail for a session.",
)
async def get_session_audit_trail(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit trail for a session."""
    service = AuditService(db)
    logs = await service.get_session_trail(session_id)

    return AuditLogListResponse(
        logs=[_audit_log_to_info(log) for log in logs],
        total=len(logs),
    )


@router.get(
    "/audit/engagement/{engagement_id}/report",
    summary="Generate engagement audit report",
    description="Generate a comprehensive audit report for an engagement.",
)
async def generate_engagement_audit_report(
    engagement_id: UUID,
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate audit report for an engagement."""
    service = AuditService(db)
    report = await service.generate_audit_report(
        engagement_id=engagement_id,
        from_date=from_date,
        to_date=to_date,
    )
    return report


# Correlation endpoint
@router.get(
    "/correlate/{trace_id}",
    summary="Correlate trace with audit logs",
    description="Get full correlation between a trace and its audit logs.",
)
async def correlate_trace_and_audit(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get correlation between trace and audit logs."""
    collector = get_trace_collector()
    audit_service = AuditService(db)

    # Get trace details
    trace_details = collector.get_trace_details(trace_id)

    # Get associated audit logs
    audit_logs = await audit_service.get_by_trace_id(trace_id)

    return {
        "trace_id": trace_id,
        "trace": trace_details,
        "audit_logs": [
            {
                "id": str(log.id),
                "action": log.action.value,
                "severity": log.severity.value,
                "resource_type": log.resource_type,
                "description": log.description,
                "created_at": log.created_at.isoformat(),
            }
            for log in audit_logs
        ],
        "correlation": {
            "trace_found": trace_details is not None,
            "audit_log_count": len(audit_logs),
            "has_span_data": trace_details is not None and len(trace_details.get("spans", [])) > 0,
            "has_audit_data": len(audit_logs) > 0,
        },
    }
