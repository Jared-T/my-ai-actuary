"""
Audit trail API routes for comprehensive audit logging and compliance.

Provides endpoints for:
- Audit trail querying and export
- Artifact verification
- Compliance report generation
- Chain integrity verification
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.audit import AuditAction, AuditSeverity
from services.audit_service import AuditService
from services.compliance_reporting_service import (
    ComplianceReportingService,
    ComplianceReportType,
    ExportFormat,
)
from services.crypto_verification_service import get_crypto_service

router = APIRouter(prefix="/audit-trail", tags=["Audit Trail"])


# Request/Response Models
class HashVerificationRequest(BaseModel):
    """Request model for hash verification."""

    content: str = Field(description="Base64-encoded content to verify")
    expected_hash: str = Field(description="Expected SHA-256 hash")


class HashVerificationResponse(BaseModel):
    """Response model for hash verification."""

    is_valid: bool = Field(description="Whether the hash matches")
    actual_hash: str = Field(description="Actual computed hash")
    expected_hash: str = Field(description="Expected hash from request")
    algorithm: str = Field(default="SHA-256", description="Hash algorithm used")


class ChainVerificationResponse(BaseModel):
    """Response model for chain integrity verification."""

    is_valid: bool = Field(description="Whether the chain is valid")
    entries_checked: int = Field(description="Number of entries verified")
    verification_timestamp: str = Field(description="When verification was performed")
    failed_at_index: Optional[int] = Field(default=None, description="Index of first invalid entry")
    error_message: Optional[str] = Field(default=None, description="Error description if invalid")
    failed_entry_id: Optional[str] = Field(default=None, description="ID of failed entry")


class AuditExportResponse(BaseModel):
    """Response model for audit export."""

    export_timestamp: str = Field(description="When export was generated")
    exported_by: str = Field(description="User who requested export")
    entry_count: int = Field(description="Number of entries exported")
    verification_hash: str = Field(description="SHA-256 hash of export data")


class ComplianceReportRequest(BaseModel):
    """Request model for compliance report generation."""

    report_type: str = Field(
        default=ComplianceReportType.FULL_AUDIT,
        description="Type of report to generate",
    )
    engagement_id: Optional[UUID] = Field(default=None, description="Filter by engagement")
    user_id: Optional[UUID] = Field(default=None, description="Filter by user (for user activity reports)")
    from_date: Optional[datetime] = Field(default=None, description="Start of date range")
    to_date: Optional[datetime] = Field(default=None, description="End of date range")
    include_artifacts: bool = Field(default=True, description="Include artifact details")
    include_verification: bool = Field(default=True, description="Include verification hashes")


class ArtifactVerificationRequest(BaseModel):
    """Request model for artifact hash verification."""

    artifact_id: UUID = Field(description="ID of the artifact to verify")
    expected_hash: str = Field(description="Expected SHA-256 hash")


class ComplianceCheckRequest(BaseModel):
    """Request model for logging compliance checks."""

    compliance_standard: str = Field(description="Compliance standard (e.g., IFRS17, SOX)")
    check_description: str = Field(description="Description of the compliance check")
    check_result: bool = Field(description="Whether the check passed")
    engagement_id: Optional[UUID] = Field(default=None, description="Associated engagement")
    resource_type: str = Field(default="compliance", description="Type of resource checked")
    resource_id: Optional[UUID] = Field(default=None, description="ID of resource checked")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Additional context")


# Endpoints
@router.get(
    "/verify-chain",
    response_model=ChainVerificationResponse,
    summary="Verify audit chain integrity",
    description="Verify the cryptographic integrity of the audit chain.",
)
async def verify_audit_chain(
    engagement_id: Optional[UUID] = Query(default=None, description="Filter by engagement"),
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
) -> ChainVerificationResponse:
    """Verify the integrity of the audit chain."""
    service = AuditService(db)
    result = await service.verify_audit_chain(
        engagement_id=engagement_id,
        from_date=from_date,
        to_date=to_date,
    )
    return ChainVerificationResponse(**result)


@router.get(
    "/export",
    summary="Export audit trail",
    description="Export the audit trail with cryptographic verification.",
)
async def export_audit_trail(
    engagement_id: Optional[UUID] = Query(default=None, description="Filter by engagement"),
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    format: str = Query(default=ExportFormat.JSON, description="Export format (json or csv)"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export the audit trail in the requested format."""
    audit_service = AuditService(db)
    compliance_service = ComplianceReportingService(db)

    export_data = await audit_service.export_audit_trail(
        engagement_id=engagement_id,
        from_date=from_date,
        to_date=to_date,
    )

    if format == ExportFormat.CSV:
        csv_content = compliance_service.export_to_csv({"events": export_data["entries"]})
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "X-Verification-Hash": export_data["verification"]["hash"],
            },
        )
    else:
        json_content = compliance_service.export_to_json(export_data)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=audit_trail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "X-Verification-Hash": export_data["verification"]["hash"],
            },
        )


@router.post(
    "/verify-hash",
    response_model=HashVerificationResponse,
    summary="Verify content hash",
    description="Verify a content hash matches the provided content.",
)
async def verify_hash(
    request: HashVerificationRequest,
) -> HashVerificationResponse:
    """Verify that content matches its expected hash."""
    import base64

    try:
        content = base64.b64decode(request.content)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")

    crypto = get_crypto_service()
    actual_hash = crypto.generate_content_hash(content)
    is_valid = crypto.verify_content_hash(content, request.expected_hash)

    return HashVerificationResponse(
        is_valid=is_valid,
        actual_hash=actual_hash,
        expected_hash=request.expected_hash,
    )


def validate_compliance_report_request(request: ComplianceReportRequest) -> None:
    """Validate required parameters for compliance report request."""
    if request.report_type == ComplianceReportType.ARTIFACT_VERIFICATION:
        if not request.engagement_id:
            raise HTTPException(
                status_code=400,
                detail="engagement_id is required for artifact verification reports",
            )
    elif request.report_type == ComplianceReportType.USER_ACTIVITY:
        if not request.user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required for user activity reports",
            )
    elif request.report_type == ComplianceReportType.APPROVAL_HISTORY:
        if not request.engagement_id:
            raise HTTPException(
                status_code=400,
                detail="engagement_id is required for approval history reports",
            )
    elif request.report_type not in [
        ComplianceReportType.FULL_AUDIT,
        ComplianceReportType.ARTIFACT_VERIFICATION,
        ComplianceReportType.USER_ACTIVITY,
        ComplianceReportType.SECURITY_EVENTS,
        ComplianceReportType.APPROVAL_HISTORY,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type: {request.report_type}",
        )


@router.post(
    "/compliance-report",
    summary="Generate compliance report",
    description="Generate a comprehensive compliance report.",
)
async def generate_compliance_report(
    request: ComplianceReportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate a compliance report based on the request parameters."""
    # Validation happens in the function body, but DB dependency is injected first
    validate_compliance_report_request(request)

    service = ComplianceReportingService(db)

    if request.report_type == ComplianceReportType.FULL_AUDIT:
        report = await service.generate_full_audit_report(
            engagement_id=request.engagement_id,
            from_date=request.from_date,
            to_date=request.to_date,
            include_artifacts=request.include_artifacts,
            include_verification=request.include_verification,
        )
    elif request.report_type == ComplianceReportType.ARTIFACT_VERIFICATION:
        report = await service.generate_artifact_verification_report(
            engagement_id=request.engagement_id,  # Already validated above
        )
    elif request.report_type == ComplianceReportType.USER_ACTIVITY:
        report = await service.generate_user_activity_report(
            user_id=request.user_id,  # Already validated above
            from_date=request.from_date,
            to_date=request.to_date,
        )
    elif request.report_type == ComplianceReportType.SECURITY_EVENTS:
        report = await service.generate_security_events_report(
            from_date=request.from_date,
            to_date=request.to_date,
        )
    else:  # ComplianceReportType.APPROVAL_HISTORY - validated above
        report = await service.generate_approval_history_report(
            engagement_id=request.engagement_id,  # Already validated above
        )

    return report


@router.get(
    "/compliance-report/{engagement_id}",
    summary="Get engagement compliance report",
    description="Get a full audit compliance report for an engagement.",
)
async def get_engagement_compliance_report(
    engagement_id: UUID,
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    format: str = Query(default=ExportFormat.JSON, description="Export format"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get a compliance report for a specific engagement."""
    service = ComplianceReportingService(db)

    report = await service.generate_full_audit_report(
        engagement_id=engagement_id,
        from_date=from_date,
        to_date=to_date,
        include_artifacts=True,
        include_verification=True,
    )

    if format == ExportFormat.CSV:
        csv_content = service.export_to_csv(report)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=compliance_report_{engagement_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            },
        )
    else:
        json_content = service.export_to_json(report)
        return Response(
            content=json_content,
            media_type="application/json",
        )


@router.get(
    "/artifact-verification/{engagement_id}",
    summary="Get artifact verification report",
    description="Get a verification report for all artifacts in an engagement.",
)
async def get_artifact_verification_report(
    engagement_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get artifact verification report for an engagement."""
    service = ComplianceReportingService(db)
    return await service.generate_artifact_verification_report(
        engagement_id=engagement_id,
    )


@router.get(
    "/user-activity/{user_id}",
    summary="Get user activity report",
    description="Get an activity report for a specific user.",
)
async def get_user_activity_report(
    user_id: UUID,
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get user activity report."""
    service = ComplianceReportingService(db)
    return await service.generate_user_activity_report(
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/security-events",
    summary="Get security events report",
    description="Get a report of security-related events.",
)
async def get_security_events_report(
    from_date: Optional[datetime] = Query(default=None, description="Start date"),
    to_date: Optional[datetime] = Query(default=None, description="End date"),
    min_severity: str = Query(default="warning", description="Minimum severity level"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get security events report."""
    try:
        severity = AuditSeverity(min_severity)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity '{min_severity}'. Valid values: {[s.value for s in AuditSeverity]}",
        )

    service = ComplianceReportingService(db)
    return await service.generate_security_events_report(
        from_date=from_date,
        to_date=to_date,
        min_severity=severity,
    )


@router.post(
    "/log-compliance-check",
    summary="Log a compliance check",
    description="Log a compliance check event to the audit trail.",
)
async def log_compliance_check(
    request: ComplianceCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Log a compliance check to the audit trail."""
    service = AuditService(db)

    action = AuditAction.COMPLIANCE_CHECK if request.check_result else AuditAction.COMPLIANCE_VIOLATION

    audit_log = await service.log_compliance_event(
        action=action,
        description=request.check_description,
        compliance_standard=request.compliance_standard,
        check_result=request.check_result,
        engagement_id=request.engagement_id,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        metadata=request.metadata,
    )

    await db.commit()

    return {
        "status": "logged",
        "audit_log_id": str(audit_log.id),
        "action": audit_log.action.value,
        "check_passed": request.check_result,
    }


@router.get(
    "/report-types",
    summary="List available report types",
    description="Get a list of available compliance report types.",
)
async def list_report_types() -> dict[str, Any]:
    """List available compliance report types."""
    return {
        "report_types": [
            {
                "type": ComplianceReportType.FULL_AUDIT,
                "name": "Full Audit Report",
                "description": "Comprehensive audit report with all events",
                "required_params": [],
                "optional_params": ["engagement_id", "from_date", "to_date"],
            },
            {
                "type": ComplianceReportType.ARTIFACT_VERIFICATION,
                "name": "Artifact Verification Report",
                "description": "Verification report for all artifacts with chain of custody",
                "required_params": ["engagement_id"],
                "optional_params": [],
            },
            {
                "type": ComplianceReportType.USER_ACTIVITY,
                "name": "User Activity Report",
                "description": "Activity report for a specific user",
                "required_params": ["user_id"],
                "optional_params": ["from_date", "to_date"],
            },
            {
                "type": ComplianceReportType.SECURITY_EVENTS,
                "name": "Security Events Report",
                "description": "Report of security-related events (warnings, errors, critical)",
                "required_params": [],
                "optional_params": ["from_date", "to_date", "min_severity"],
            },
            {
                "type": ComplianceReportType.APPROVAL_HISTORY,
                "name": "Approval History Report",
                "description": "Report of all approval-related actions for an engagement",
                "required_params": ["engagement_id"],
                "optional_params": [],
            },
        ],
        "export_formats": [ExportFormat.JSON, ExportFormat.CSV],
    }


@router.get(
    "/hash-algorithms",
    summary="List supported hash algorithms",
    description="Get information about supported hash algorithms.",
)
async def list_hash_algorithms() -> dict[str, Any]:
    """List supported hash algorithms and their properties."""
    return {
        "algorithms": [
            {
                "name": "SHA-256",
                "hash_length": 64,
                "description": "SHA-256 is used for all content hashing and verification",
                "use_cases": ["artifact_content", "report_verification", "chain_integrity"],
            },
            {
                "name": "HMAC-SHA256",
                "hash_length": 64,
                "description": "HMAC-SHA256 is used for audit chain signatures",
                "use_cases": ["audit_signatures", "chain_verification"],
            },
        ],
        "default_algorithm": "SHA-256",
    }
