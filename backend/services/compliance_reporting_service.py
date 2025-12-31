"""
Compliance reporting service for audit trail system.

Provides:
- Comprehensive compliance report generation
- Multiple export formats (JSON, CSV)
- Artifact verification reports
- Regulatory compliance summaries
- Chain of custody documentation
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.tracing import get_current_trace_id
from models.artefact import Artefact, ArtefactStatus
from models.audit import AuditAction, AuditLog, AuditSeverity
from services.crypto_verification_service import get_crypto_service

logger = get_logger(__name__)


class ComplianceReportType:
    """Types of compliance reports available."""

    FULL_AUDIT = "full_audit"
    ARTIFACT_VERIFICATION = "artifact_verification"
    USER_ACTIVITY = "user_activity"
    WORKFLOW_SUMMARY = "workflow_summary"
    SECURITY_EVENTS = "security_events"
    CHAIN_OF_CUSTODY = "chain_of_custody"
    APPROVAL_HISTORY = "approval_history"


class ExportFormat:
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"


class ComplianceReportingService:
    """
    Service for generating compliance reports from audit data.

    Provides comprehensive reporting for regulatory compliance,
    internal audits, and forensic analysis.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the compliance reporting service.

        Args:
            db: Database session for data access
        """
        self.db = db
        self.crypto = get_crypto_service()

    async def generate_full_audit_report(
        self,
        engagement_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        include_artifacts: bool = True,
        include_verification: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a comprehensive audit report.

        Args:
            engagement_id: Filter by engagement (optional)
            from_date: Start of date range
            to_date: End of date range
            include_artifacts: Include artifact details
            include_verification: Include cryptographic verification

        Returns:
            Complete audit report with all details
        """
        now = datetime.now(timezone.utc)
        from_date = from_date or (now - timedelta(days=30))
        to_date = to_date or now

        # Build query conditions
        conditions = [
            AuditLog.created_at >= from_date,
            AuditLog.created_at <= to_date,
        ]
        if engagement_id:
            conditions.append(AuditLog.engagement_id == engagement_id)

        # Fetch audit logs
        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        # Collect statistics
        action_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        resource_types: dict[str, int] = {}
        unique_users: set[str] = set()
        unique_sessions: set[str] = set()

        events = []
        for log in logs:
            action_counts[log.action.value] = action_counts.get(log.action.value, 0) + 1
            severity_counts[log.severity.value] = severity_counts.get(log.severity.value, 0) + 1
            resource_types[log.resource_type] = resource_types.get(log.resource_type, 0) + 1

            if log.user_id:
                unique_users.add(str(log.user_id))
            if log.session_id:
                unique_sessions.add(str(log.session_id))

            events.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "action": log.action.value,
                "severity": log.severity.value,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "description": log.description,
                "user_id": str(log.user_id) if log.user_id else None,
                "session_id": str(log.session_id) if log.session_id else None,
                "trace_id": log.trace_id,
                "ip_address": log.ip_address,
                "metadata": log.extra_metadata,
            })

        # Build report
        report = {
            "report_type": ComplianceReportType.FULL_AUDIT,
            "generated_at": now.isoformat(),
            "report_period": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            },
            "filters": {
                "engagement_id": str(engagement_id) if engagement_id else None,
            },
            "summary": {
                "total_events": len(logs),
                "unique_users": len(unique_users),
                "unique_sessions": len(unique_sessions),
                "events_by_action": action_counts,
                "events_by_severity": severity_counts,
                "events_by_resource_type": resource_types,
            },
            "events": events,
        }

        # Add artifact details if requested
        if include_artifacts and engagement_id:
            artifacts = await self._get_artifact_summary(engagement_id, from_date, to_date)
            report["artifacts"] = artifacts

        # Add verification hash
        if include_verification:
            report["verification"] = {
                "hash": self.crypto.generate_report_hash(report, now),
                "algorithm": "SHA-256",
            }

        logger.info(
            "Generated full audit report",
            event_count=len(logs),
            engagement_id=str(engagement_id) if engagement_id else None,
        )

        return report

    async def generate_artifact_verification_report(
        self,
        engagement_id: UUID,
        verify_hashes: bool = True,
    ) -> dict[str, Any]:
        """
        Generate an artifact verification report.

        Checks all artifacts for integrity and provides chain of custody.

        Args:
            engagement_id: Engagement to report on
            verify_hashes: Whether to verify content hashes (requires storage access)

        Returns:
            Artifact verification report
        """
        now = datetime.now(timezone.utc)

        # Fetch artifacts
        stmt = (
            select(Artefact)
            .where(
                and_(
                    Artefact.engagement_id == engagement_id,
                    Artefact.is_deleted == False,
                )
            )
            .order_by(Artefact.created_at)
        )
        result = await self.db.execute(stmt)
        artifacts = list(result.scalars().all())

        # Get related audit logs for each artifact
        artifact_details = []
        for artifact in artifacts:
            audit_stmt = (
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.resource_type == "artefact",
                        AuditLog.resource_id == artifact.id,
                    )
                )
                .order_by(AuditLog.created_at)
            )
            audit_result = await self.db.execute(audit_stmt)
            artifact_logs = list(audit_result.scalars().all())

            fingerprint = self.crypto.generate_artifact_fingerprint(
                content_hash=artifact.content_hash,
                file_name=artifact.file_name,
                file_size=artifact.file_size,
                created_at=artifact.created_at,
            )

            artifact_details.append({
                "id": str(artifact.id),
                "name": artifact.name,
                "file_name": artifact.file_name,
                "type": artifact.artefact_type.value,
                "status": artifact.status.value,
                "version": artifact.version,
                "file_size": artifact.file_size,
                "mime_type": artifact.mime_type,
                "created_at": artifact.created_at.isoformat(),
                "created_by": str(artifact.created_by) if artifact.created_by else None,
                "verification": {
                    "content_hash": artifact.content_hash,
                    "fingerprint": fingerprint,
                    "algorithm": "SHA-256",
                    "hash_verified": None,  # Would require storage access to verify
                },
                "chain_of_custody": [
                    {
                        "timestamp": log.created_at.isoformat(),
                        "action": log.action.value,
                        "user_id": str(log.user_id) if log.user_id else None,
                        "description": log.description,
                    }
                    for log in artifact_logs
                ],
                "previous_version_id": str(artifact.previous_version_id) if artifact.previous_version_id else None,
            })

        # Count by status
        status_counts = {}
        for artifact in artifacts:
            status = artifact.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        report = {
            "report_type": ComplianceReportType.ARTIFACT_VERIFICATION,
            "generated_at": now.isoformat(),
            "engagement_id": str(engagement_id),
            "summary": {
                "total_artifacts": len(artifacts),
                "artifacts_by_status": status_counts,
                "total_file_size_bytes": sum(a.file_size for a in artifacts),
            },
            "artifacts": artifact_details,
            "verification": {
                "hash": self.crypto.generate_report_hash(
                    {"artifacts": [a["id"] for a in artifact_details]},
                    now,
                ),
                "algorithm": "SHA-256",
            },
        }

        logger.info(
            "Generated artifact verification report",
            engagement_id=str(engagement_id),
            artifact_count=len(artifacts),
        )

        return report

    async def generate_user_activity_report(
        self,
        user_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Generate a user activity report.

        Args:
            user_id: User to report on
            from_date: Start of date range
            to_date: End of date range

        Returns:
            User activity report
        """
        now = datetime.now(timezone.utc)
        from_date = from_date or (now - timedelta(days=30))
        to_date = to_date or now

        # Fetch user's audit logs
        stmt = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= from_date,
                    AuditLog.created_at <= to_date,
                )
            )
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        # Analyze activity patterns
        action_counts: dict[str, int] = {}
        engagement_activity: dict[str, int] = {}
        session_activity: dict[str, int] = {}
        hourly_distribution: dict[int, int] = {}

        for log in logs:
            action_counts[log.action.value] = action_counts.get(log.action.value, 0) + 1

            if log.engagement_id:
                eid = str(log.engagement_id)
                engagement_activity[eid] = engagement_activity.get(eid, 0) + 1

            if log.session_id:
                sid = str(log.session_id)
                session_activity[sid] = session_activity.get(sid, 0) + 1

            hour = log.created_at.hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1

        report = {
            "report_type": ComplianceReportType.USER_ACTIVITY,
            "generated_at": now.isoformat(),
            "user_id": str(user_id),
            "report_period": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            },
            "summary": {
                "total_actions": len(logs),
                "unique_engagements": len(engagement_activity),
                "unique_sessions": len(session_activity),
            },
            "activity_breakdown": {
                "by_action": action_counts,
                "by_engagement": engagement_activity,
                "by_hour": {str(h): c for h, c in sorted(hourly_distribution.items())},
            },
            "timeline": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "action": log.action.value,
                    "resource_type": log.resource_type,
                    "description": log.description,
                    "ip_address": log.ip_address,
                }
                for log in logs
            ],
            "verification": {
                "hash": self.crypto.generate_report_hash(
                    {"user_id": str(user_id), "action_count": len(logs)},
                    now,
                ),
                "algorithm": "SHA-256",
            },
        }

        logger.info(
            "Generated user activity report",
            user_id=str(user_id),
            action_count=len(logs),
        )

        return report

    async def generate_security_events_report(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        min_severity: AuditSeverity = AuditSeverity.WARNING,
    ) -> dict[str, Any]:
        """
        Generate a security events report.

        Focuses on warnings, errors, and critical events.

        Args:
            from_date: Start of date range
            to_date: End of date range
            min_severity: Minimum severity level to include

        Returns:
            Security events report
        """
        now = datetime.now(timezone.utc)
        from_date = from_date or (now - timedelta(days=7))
        to_date = to_date or now

        # Map severity to ordering for comparison
        severity_order = {
            AuditSeverity.INFO: 0,
            AuditSeverity.WARNING: 1,
            AuditSeverity.ERROR: 2,
            AuditSeverity.CRITICAL: 3,
        }
        min_order = severity_order[min_severity]

        # Fetch security-relevant logs
        stmt = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.created_at <= to_date,
                )
            )
            .order_by(desc(AuditLog.severity), desc(AuditLog.created_at))
        )
        result = await self.db.execute(stmt)
        all_logs = list(result.scalars().all())

        # Filter by severity
        logs = [
            log for log in all_logs
            if severity_order.get(log.severity, 0) >= min_order
        ]

        # Categorize events
        critical_events = [log for log in logs if log.severity == AuditSeverity.CRITICAL]
        error_events = [log for log in logs if log.severity == AuditSeverity.ERROR]
        warning_events = [log for log in logs if log.severity == AuditSeverity.WARNING]

        def log_to_dict(log: AuditLog) -> dict[str, Any]:
            return {
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "action": log.action.value,
                "severity": log.severity.value,
                "resource_type": log.resource_type,
                "description": log.description,
                "user_id": str(log.user_id) if log.user_id else None,
                "ip_address": log.ip_address,
                "trace_id": log.trace_id,
            }

        report = {
            "report_type": ComplianceReportType.SECURITY_EVENTS,
            "generated_at": now.isoformat(),
            "report_period": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
            },
            "filters": {
                "min_severity": min_severity.value,
            },
            "summary": {
                "total_events": len(logs),
                "critical_count": len(critical_events),
                "error_count": len(error_events),
                "warning_count": len(warning_events),
            },
            "critical_events": [log_to_dict(log) for log in critical_events],
            "error_events": [log_to_dict(log) for log in error_events],
            "warning_events": [log_to_dict(log) for log in warning_events[:50]],  # Limit warnings
            "verification": {
                "hash": self.crypto.generate_report_hash(
                    {"total_events": len(logs), "critical": len(critical_events)},
                    now,
                ),
                "algorithm": "SHA-256",
            },
        }

        logger.info(
            "Generated security events report",
            total_events=len(logs),
            critical=len(critical_events),
            error=len(error_events),
        )

        return report

    async def generate_approval_history_report(
        self,
        engagement_id: UUID,
    ) -> dict[str, Any]:
        """
        Generate an approval history report.

        Shows all approval-related actions for an engagement.

        Args:
            engagement_id: Engagement to report on

        Returns:
            Approval history report
        """
        now = datetime.now(timezone.utc)

        # Fetch approval-related audit logs
        approval_actions = [
            AuditAction.APPROVAL_REQUEST,
            AuditAction.APPROVAL_APPROVE,
            AuditAction.APPROVAL_REJECT,
            AuditAction.APPROVAL_REVOKE,
        ]

        stmt = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.engagement_id == engagement_id,
                    AuditLog.action.in_(approval_actions),
                )
            )
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        # Group by resource
        by_resource: dict[str, list[dict[str, Any]]] = {}
        for log in logs:
            resource_key = f"{log.resource_type}:{log.resource_id}" if log.resource_id else log.resource_type
            if resource_key not in by_resource:
                by_resource[resource_key] = []

            by_resource[resource_key].append({
                "timestamp": log.created_at.isoformat(),
                "action": log.action.value,
                "user_id": str(log.user_id) if log.user_id else None,
                "description": log.description,
                "metadata": log.extra_metadata,
            })

        # Count outcomes
        approved_count = len([log for log in logs if log.action == AuditAction.APPROVAL_APPROVE])
        rejected_count = len([log for log in logs if log.action == AuditAction.APPROVAL_REJECT])
        pending_count = len([log for log in logs if log.action == AuditAction.APPROVAL_REQUEST]) - approved_count - rejected_count

        report = {
            "report_type": ComplianceReportType.APPROVAL_HISTORY,
            "generated_at": now.isoformat(),
            "engagement_id": str(engagement_id),
            "summary": {
                "total_approval_events": len(logs),
                "approved": approved_count,
                "rejected": rejected_count,
                "pending": max(0, pending_count),
                "unique_resources": len(by_resource),
            },
            "approval_history_by_resource": by_resource,
            "verification": {
                "hash": self.crypto.generate_report_hash(
                    {"engagement_id": str(engagement_id), "total": len(logs)},
                    now,
                ),
                "algorithm": "SHA-256",
            },
        }

        logger.info(
            "Generated approval history report",
            engagement_id=str(engagement_id),
            event_count=len(logs),
        )

        return report

    async def _get_artifact_summary(
        self,
        engagement_id: UUID,
        from_date: datetime,
        to_date: datetime,
    ) -> dict[str, Any]:
        """Get artifact summary for an engagement."""
        stmt = (
            select(Artefact)
            .where(
                and_(
                    Artefact.engagement_id == engagement_id,
                    Artefact.created_at >= from_date,
                    Artefact.created_at <= to_date,
                    Artefact.is_deleted == False,
                )
            )
            .order_by(Artefact.created_at)
        )
        result = await self.db.execute(stmt)
        artifacts = list(result.scalars().all())

        return {
            "count": len(artifacts),
            "total_size_bytes": sum(a.file_size for a in artifacts),
            "by_type": self._count_by_attribute(artifacts, "artefact_type"),
            "by_status": self._count_by_attribute(artifacts, "status"),
            "items": [
                {
                    "id": str(a.id),
                    "name": a.name,
                    "type": a.artefact_type.value,
                    "status": a.status.value,
                    "content_hash": a.content_hash,
                }
                for a in artifacts
            ],
        }

    @staticmethod
    def _count_by_attribute(items: list[Any], attr: str) -> dict[str, int]:
        """Count items by an attribute value."""
        counts: dict[str, int] = {}
        for item in items:
            value = getattr(item, attr)
            if hasattr(value, "value"):
                value = value.value
            counts[value] = counts.get(value, 0) + 1
        return counts

    def export_to_csv(self, report: dict[str, Any]) -> str:
        """
        Export report events to CSV format.

        Args:
            report: Report dictionary with 'events' or 'timeline' key

        Returns:
            CSV formatted string
        """
        output = io.StringIO()
        events = report.get("events") or report.get("timeline") or []

        if not events:
            return ""

        # Get all keys from first event for headers
        headers = list(events[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for event in events:
            # Flatten nested dicts for CSV
            flat_event = {}
            for key, value in event.items():
                if isinstance(value, dict):
                    flat_event[key] = json.dumps(value)
                else:
                    flat_event[key] = value
            writer.writerow(flat_event)

        return output.getvalue()

    def export_to_json(self, report: dict[str, Any], pretty: bool = True) -> str:
        """
        Export report to JSON format.

        Args:
            report: Report dictionary
            pretty: Whether to format with indentation

        Returns:
            JSON formatted string
        """
        if pretty:
            return json.dumps(report, indent=2, default=str)
        return json.dumps(report, default=str)


async def get_compliance_service(db: AsyncSession) -> ComplianceReportingService:
    """
    FastAPI dependency for getting a ComplianceReportingService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured ComplianceReportingService instance
    """
    return ComplianceReportingService(db)
