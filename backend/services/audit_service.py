"""
Audit trail service for comprehensive activity logging.

Provides:
- Audit log creation and management
- Integration with distributed tracing
- Query and retrieval of audit records
- Compliance-ready audit trail generation
- Cryptographic verification and artifact hashing
- Chain integrity verification
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.tracing import get_current_trace_id
from models.audit import AuditAction, AuditLog, AuditSeverity
from services.crypto_verification_service import get_crypto_service, CryptoVerificationService

logger = get_logger(__name__)


class AuditService:
    """
    Service for managing audit trails across the application.

    Provides comprehensive audit logging with trace correlation
    for compliance and debugging purposes. Includes cryptographic
    verification for audit chain integrity.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the audit service.

        Args:
            db: Database session for persistence operations
        """
        self.db = db
        self.crypto = get_crypto_service()

    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        description: str,
        user_id: Optional[UUID] = None,
        resource_id: Optional[UUID] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[UUID] = None,
        engagement_id: Optional[UUID] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Automatically captures trace context if not provided.

        Args:
            action: The audit action type
            resource_type: Type of resource being acted upon
            description: Human-readable description
            user_id: ID of the user performing the action
            resource_id: ID of the resource being acted upon
            old_value: Previous state before change
            new_value: New state after change
            metadata: Additional context information
            trace_id: Trace ID for correlation (auto-captured if not provided)
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session ID if applicable
            engagement_id: Engagement ID if applicable
            severity: Severity level of the event

        Returns:
            Created AuditLog record
        """
        # Auto-capture trace ID from current context if not provided
        if trace_id is None:
            trace_id = get_current_trace_id()

        audit_log = AuditLog.create(
            action=action,
            resource_type=resource_type,
            description=description,
            user_id=user_id,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata,
            trace_id=trace_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            engagement_id=engagement_id,
            severity=severity,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.info(
            "Audit log created",
            action=action.value,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            trace_id=trace_id,
        )

        return audit_log

    async def log_agent_action(
        self,
        action: AuditAction,
        agent_name: str,
        description: str,
        user_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        engagement_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Create an audit log entry for agent actions.

        Convenience method for logging agent-related events with
        standardized metadata.

        Args:
            action: The audit action (AGENT_INVOKE, AGENT_COMPLETE, AGENT_ERROR)
            agent_name: Name of the agent
            description: Action description
            user_id: User who triggered the action
            session_id: Session ID
            engagement_id: Engagement ID
            trace_id: Trace ID for correlation
            model: Model used by the agent
            tokens_used: Number of tokens consumed
            metadata: Additional metadata

        Returns:
            Created AuditLog record
        """
        agent_metadata = {
            "agent_name": agent_name,
            "model": model,
            "tokens_used": tokens_used,
            **(metadata or {}),
        }

        return await self.log(
            action=action,
            resource_type="agent",
            description=description,
            user_id=user_id,
            metadata=agent_metadata,
            trace_id=trace_id,
            session_id=session_id,
            engagement_id=engagement_id,
        )

    async def get_by_trace_id(self, trace_id: str) -> list[AuditLog]:
        """
        Get all audit logs associated with a trace ID.

        Args:
            trace_id: The trace ID to search for

        Returns:
            List of audit logs for the trace
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.trace_id == trace_id)
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        action: Optional[AuditAction] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific user.

        Args:
            user_id: The user ID to search for
            limit: Maximum number of records to return
            offset: Number of records to skip
            action: Filter by specific action type
            from_date: Start of date range
            to_date: End of date range

        Returns:
            List of audit logs for the user
        """
        conditions = [AuditLog.user_id == user_id]

        if action:
            conditions.append(AuditLog.action == action)
        if from_date:
            conditions.append(AuditLog.created_at >= from_date)
        if to_date:
            conditions.append(AuditLog.created_at <= to_date)

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(desc(AuditLog.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_resource(
        self,
        resource_type: str,
        resource_id: UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """
        Get audit logs for a specific resource.

        Args:
            resource_type: Type of the resource
            resource_id: ID of the resource
            limit: Maximum number of records to return

        Returns:
            List of audit logs for the resource
        """
        stmt = (
            select(AuditLog)
            .where(
                and_(
                    AuditLog.resource_type == resource_type,
                    AuditLog.resource_id == resource_id,
                )
            )
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(
        self,
        limit: int = 100,
        severity: Optional[AuditSeverity] = None,
        action: Optional[AuditAction] = None,
    ) -> list[AuditLog]:
        """
        Get recent audit logs with optional filtering.

        Args:
            limit: Maximum number of records to return
            severity: Filter by severity level
            action: Filter by action type

        Returns:
            List of recent audit logs
        """
        conditions = []

        if severity:
            conditions.append(AuditLog.severity == severity)
        if action:
            conditions.append(AuditLog.action == action)

        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_session_trail(
        self,
        session_id: UUID,
    ) -> list[AuditLog]:
        """
        Get the complete audit trail for a session.

        Args:
            session_id: The session ID

        Returns:
            Chronological list of audit logs for the session
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.session_id == session_id)
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_engagement_trail(
        self,
        engagement_id: UUID,
    ) -> list[AuditLog]:
        """
        Get the complete audit trail for an engagement.

        Args:
            engagement_id: The engagement ID

        Returns:
            Chronological list of audit logs for the engagement
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.engagement_id == engagement_id)
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_statistics(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Get audit log statistics.

        Args:
            from_date: Start of date range
            to_date: End of date range

        Returns:
            Dictionary with audit statistics
        """
        from sqlalchemy import func

        # Default to last 24 hours if no date range provided
        if from_date is None:
            from_date = datetime.now(timezone.utc) - timedelta(days=1)
        if to_date is None:
            to_date = datetime.now(timezone.utc)

        # Count by action
        action_counts_stmt = (
            select(AuditLog.action, func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.created_at <= to_date,
                )
            )
            .group_by(AuditLog.action)
        )
        action_result = await self.db.execute(action_counts_stmt)
        action_counts = {row[0].value: row[1] for row in action_result.all()}

        # Count by severity
        severity_counts_stmt = (
            select(AuditLog.severity, func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.created_at <= to_date,
                )
            )
            .group_by(AuditLog.severity)
        )
        severity_result = await self.db.execute(severity_counts_stmt)
        severity_counts = {row[0].value: row[1] for row in severity_result.all()}

        # Total count
        total_stmt = (
            select(func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.created_at >= from_date,
                    AuditLog.created_at <= to_date,
                )
            )
        )
        total_result = await self.db.execute(total_stmt)
        total_count = total_result.scalar() or 0

        return {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "total_count": total_count,
            "by_action": action_counts,
            "by_severity": severity_counts,
        }

    async def generate_audit_report(
        self,
        engagement_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Generate a comprehensive audit report for an engagement.

        Useful for compliance reporting and professional review.

        Args:
            engagement_id: The engagement ID
            from_date: Start of date range
            to_date: End of date range

        Returns:
            Comprehensive audit report
        """
        conditions = [AuditLog.engagement_id == engagement_id]

        if from_date:
            conditions.append(AuditLog.created_at >= from_date)
        if to_date:
            conditions.append(AuditLog.created_at <= to_date)

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(AuditLog.created_at)
        )
        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        # Group by action type
        actions_by_type: dict[str, list[dict[str, Any]]] = {}
        for log in logs:
            action_type = log.action.value
            if action_type not in actions_by_type:
                actions_by_type[action_type] = []

            actions_by_type[action_type].append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "description": log.description,
                "user_id": str(log.user_id) if log.user_id else None,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "trace_id": log.trace_id,
                "severity": log.severity.value,
            })

        # Calculate summary
        unique_users = set(str(log.user_id) for log in logs if log.user_id)
        unique_traces = set(log.trace_id for log in logs if log.trace_id)

        now = datetime.now(timezone.utc)
        report = {
            "engagement_id": str(engagement_id),
            "report_generated_at": now.isoformat(),
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "summary": {
                "total_events": len(logs),
                "unique_users": len(unique_users),
                "unique_traces": len(unique_traces),
                "event_types": list(actions_by_type.keys()),
            },
            "events_by_type": actions_by_type,
            "timeline": [
                {
                    "id": str(log.id),
                    "timestamp": log.created_at.isoformat(),
                    "action": log.action.value,
                    "description": log.description,
                    "severity": log.severity.value,
                    "trace_id": log.trace_id,
                }
                for log in logs
            ],
        }

        # Add verification hash
        report["verification"] = {
            "hash": self.crypto.generate_report_hash(report, now),
            "algorithm": "SHA-256",
        }

        return report

    async def log_artifact_operation(
        self,
        action: AuditAction,
        artifact_id: UUID,
        artifact_name: str,
        content_hash: str,
        description: str,
        user_id: Optional[UUID] = None,
        engagement_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        verified: bool = False,
    ) -> AuditLog:
        """
        Log an artifact operation with cryptographic verification.

        Creates an audit entry specifically for artifact actions with
        hash verification and integrity tracking.

        Args:
            action: The artifact action type
            artifact_id: ID of the artifact
            artifact_name: Name of the artifact
            content_hash: SHA-256 hash of artifact content
            description: Action description
            user_id: User performing the action
            engagement_id: Associated engagement
            session_id: Associated session
            metadata: Additional metadata
            verified: Whether the content hash was verified

        Returns:
            Created AuditLog record
        """
        artifact_metadata = {
            "artifact_name": artifact_name,
            "content_hash": content_hash,
            "hash_verified": verified,
            "hash_algorithm": "SHA-256",
            **(metadata or {}),
        }

        return await self.log(
            action=action,
            resource_type="artefact",
            resource_id=artifact_id,
            description=description,
            user_id=user_id,
            engagement_id=engagement_id,
            session_id=session_id,
            metadata=artifact_metadata,
        )

    async def verify_artifact_hash(
        self,
        artifact_id: UUID,
        content: bytes,
        expected_hash: str,
        user_id: Optional[UUID] = None,
        engagement_id: Optional[UUID] = None,
    ) -> tuple[bool, AuditLog]:
        """
        Verify artifact content hash and log the verification.

        Args:
            artifact_id: ID of the artifact
            content: Artifact binary content
            expected_hash: Expected SHA-256 hash
            user_id: User performing verification
            engagement_id: Associated engagement

        Returns:
            Tuple of (verification_result, audit_log)
        """
        is_valid = self.crypto.verify_content_hash(content, expected_hash)
        actual_hash = self.crypto.generate_content_hash(content)

        if is_valid:
            action = AuditAction.ARTEFACT_VERIFY
            severity = AuditSeverity.INFO
            description = "Artifact hash verification successful"
        else:
            action = AuditAction.ARTEFACT_HASH_MISMATCH
            severity = AuditSeverity.ERROR
            description = "Artifact hash verification FAILED - content may be corrupted or tampered"

        audit_log = await self.log(
            action=action,
            resource_type="artefact",
            resource_id=artifact_id,
            description=description,
            user_id=user_id,
            engagement_id=engagement_id,
            severity=severity,
            metadata={
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "hash_match": is_valid,
                "algorithm": "SHA-256",
            },
        )

        logger.info(
            "Artifact hash verification",
            artifact_id=str(artifact_id),
            is_valid=is_valid,
        )

        return is_valid, audit_log

    async def log_compliance_event(
        self,
        action: AuditAction,
        description: str,
        compliance_standard: str,
        check_result: bool,
        user_id: Optional[UUID] = None,
        engagement_id: Optional[UUID] = None,
        resource_type: str = "compliance",
        resource_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log a compliance-related event.

        Args:
            action: The compliance action type
            description: Event description
            compliance_standard: Standard being checked (e.g., "IFRS17", "SOX")
            check_result: Whether the compliance check passed
            user_id: User who triggered the check
            engagement_id: Associated engagement
            resource_type: Type of resource being checked
            resource_id: ID of resource being checked
            metadata: Additional context

        Returns:
            Created AuditLog record
        """
        severity = AuditSeverity.INFO if check_result else AuditSeverity.WARNING

        compliance_metadata = {
            "compliance_standard": compliance_standard,
            "check_passed": check_result,
            "check_timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        return await self.log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            user_id=user_id,
            engagement_id=engagement_id,
            severity=severity,
            metadata=compliance_metadata,
        )

    async def get_audit_chain(
        self,
        engagement_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get audit entries with chain verification data.

        Retrieves audit entries in a format suitable for chain
        integrity verification.

        Args:
            engagement_id: Filter by engagement
            from_date: Start of date range
            to_date: End of date range
            limit: Maximum entries to return

        Returns:
            List of audit entries with verification data
        """
        conditions = []
        if engagement_id:
            conditions.append(AuditLog.engagement_id == engagement_id)
        if from_date:
            conditions.append(AuditLog.created_at >= from_date)
        if to_date:
            conditions.append(AuditLog.created_at <= to_date)

        stmt = select(AuditLog).order_by(AuditLog.created_at).limit(limit)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        # Build chain with signatures
        chain = []
        previous_signature = None

        for log in logs:
            signature = self.crypto.generate_audit_signature(
                audit_id=log.id,
                action=log.action.value,
                resource_type=log.resource_type,
                timestamp=log.created_at,
                user_id=log.user_id,
                previous_signature=previous_signature,
            )

            chain.append({
                "id": log.id,
                "action": log.action.value,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "created_at": log.created_at,
                "user_id": log.user_id,
                "description": log.description,
                "signature": signature,
                "previous_signature": previous_signature,
            })

            previous_signature = signature

        return chain

    async def verify_audit_chain(
        self,
        engagement_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Verify the integrity of an audit chain.

        Checks that all entries in the chain have valid signatures
        and proper chaining.

        Args:
            engagement_id: Filter by engagement
            from_date: Start of date range
            to_date: End of date range

        Returns:
            Verification result with details
        """
        chain = await self.get_audit_chain(
            engagement_id=engagement_id,
            from_date=from_date,
            to_date=to_date,
        )

        if not chain:
            return {
                "is_valid": True,
                "message": "No audit entries to verify",
                "entries_checked": 0,
            }

        is_valid, failed_index, error_message = self.crypto.verify_chain_integrity(chain)

        result = {
            "is_valid": is_valid,
            "entries_checked": len(chain),
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if not is_valid:
            result["failed_at_index"] = failed_index
            result["error_message"] = error_message
            result["failed_entry_id"] = str(chain[failed_index]["id"]) if failed_index is not None else None

            logger.error(
                "Audit chain verification failed",
                failed_index=failed_index,
                error=error_message,
            )
        else:
            logger.info(
                "Audit chain verification successful",
                entries_verified=len(chain),
            )

        return result

    async def export_audit_trail(
        self,
        engagement_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        user_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """
        Export audit trail with verification metadata.

        Creates an exportable audit trail with cryptographic
        verification for compliance purposes.

        Args:
            engagement_id: Filter by engagement
            from_date: Start of date range
            to_date: End of date range
            user_id: User requesting the export

        Returns:
            Exportable audit trail with verification
        """
        chain = await self.get_audit_chain(
            engagement_id=engagement_id,
            from_date=from_date,
            to_date=to_date,
        )

        now = datetime.now(timezone.utc)

        # Convert datetime objects to strings for JSON serialization
        serializable_chain = []
        for entry in chain:
            serializable_entry = {
                **entry,
                "id": str(entry["id"]),
                "created_at": entry["created_at"].isoformat(),
                "user_id": str(entry["user_id"]) if entry["user_id"] else None,
                "resource_id": str(entry["resource_id"]) if entry["resource_id"] else None,
            }
            serializable_chain.append(serializable_entry)

        export_data = {
            "export_timestamp": now.isoformat(),
            "exported_by": str(user_id) if user_id else "system",
            "filters": {
                "engagement_id": str(engagement_id) if engagement_id else None,
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
            },
            "entry_count": len(chain),
            "entries": serializable_chain,
        }

        # Generate verification hash for the export
        export_data["verification"] = {
            "hash": self.crypto.generate_report_hash(export_data, now, user_id),
            "algorithm": "SHA-256",
        }

        # Log the export action
        await self.log(
            action=AuditAction.AUDIT_EXPORT,
            resource_type="audit_trail",
            description=f"Audit trail exported with {len(chain)} entries",
            user_id=user_id,
            engagement_id=engagement_id,
            metadata={
                "entry_count": len(chain),
                "export_hash": export_data["verification"]["hash"],
            },
        )

        return export_data


# Dependency injection helper for FastAPI
async def get_audit_service(db: AsyncSession) -> AuditService:
    """
    FastAPI dependency for getting an AuditService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured AuditService instance
    """
    return AuditService(db)
