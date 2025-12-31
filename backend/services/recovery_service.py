"""
Recovery service for restoring data from backups.

Provides functionality for:
- Validating backup files before restoration
- Selective table restoration
- Engagement-level recovery
- Pre-recovery snapshots for rollback capability
- Full system recovery procedures
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from models.audit import AuditAction, AuditLog, AuditSeverity
from models.backup import Backup, BackupStatus, Recovery, RecoveryStatus

from services.backup_service import ALLOWED_BACKUP_TABLES, get_backup_dir

logger = get_logger(__name__)


def _validate_table_name(table_name: str) -> None:
    """
    Validate that a table name is in the allowed whitelist.

    Args:
        table_name: Table name to validate

    Raises:
        ValueError: If table name is not in the whitelist
    """
    if table_name not in ALLOWED_BACKUP_TABLES:
        raise ValueError(f"Invalid table name: {table_name}. Must be one of: {sorted(ALLOWED_BACKUP_TABLES)}")


class RecoveryService:
    """
    Service for managing recovery operations from backups.

    Provides methods for validating backups, restoring data,
    and handling rollback scenarios.
    """

    def __init__(self, db: AsyncSession, backup_dir: Path | None = None) -> None:
        """
        Initialize the recovery service.

        Args:
            db: Database session for operations
            backup_dir: Optional custom backup directory
        """
        self.db = db
        self.backup_dir = backup_dir or get_backup_dir()

    async def get_backup(self, backup_id: UUID) -> Backup | None:
        """Get a backup by ID."""
        from sqlalchemy import select

        stmt = select(Backup).where(Backup.id == backup_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_recovery(
        self,
        backup_id: UUID,
        name: str | None = None,
        description: str | None = None,
        user_id: UUID | None = None,
        engagement_id: UUID | None = None,
        options: dict[str, Any] | None = None,
    ) -> Recovery:
        """
        Create a new recovery operation record.

        Args:
            backup_id: Source backup ID
            name: Optional custom name for the recovery
            description: Optional description
            user_id: User initiating the recovery
            engagement_id: Optional target engagement for selective recovery
            options: Recovery options (overwrite, merge, etc.)

        Returns:
            Created Recovery record
        """
        # Validate backup exists
        backup = await self.get_backup(backup_id)
        if not backup:
            raise ValueError(f"Backup not found: {backup_id}")

        if backup.status != BackupStatus.COMPLETED:
            raise ValueError(f"Cannot recover from backup with status: {backup.status.value}")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        recovery_name = name or f"recovery_{backup.backup_type.value}_{timestamp}"

        recovery = Recovery(
            name=recovery_name,
            description=description,
            backup_id=backup_id,
            status=RecoveryStatus.PENDING,
            engagement_id=engagement_id,
            options=options or {},
            created_by=user_id,
            updated_by=user_id,
            extra_metadata={
                "environment": settings.environment,
                "app_version": settings.app_version,
                "source_backup_name": backup.name,
                "initiated_by": str(user_id) if user_id else "system",
            },
        )
        self.db.add(recovery)
        await self.db.flush()

        logger.info(
            "Recovery created",
            recovery_id=str(recovery.id),
            backup_id=str(backup_id),
            name=recovery_name,
        )

        return recovery

    async def execute_recovery(
        self,
        recovery: Recovery,
        tables_to_restore: list[str] | None = None,
    ) -> Recovery:
        """
        Execute a recovery operation.

        Args:
            recovery: Recovery record to execute
            tables_to_restore: Optional list of specific tables to restore

        Returns:
            Updated Recovery record with results
        """
        recovery.start()
        await self.db.flush()

        backup = await self.get_backup(recovery.backup_id)
        if not backup or not backup.storage_path:
            recovery.fail("Backup or backup file not found")
            await self.db.flush()
            return recovery

        try:
            # Create pre-recovery snapshot if configured
            snapshot_path = await self._create_pre_recovery_snapshot(recovery, backup)
            if snapshot_path:
                recovery.pre_recovery_snapshot = str(snapshot_path)
                await self.db.flush()

            # Load backup data
            backup_data = self._load_backup_file(backup.storage_path)
            if not backup_data:
                recovery.fail("Failed to load backup file")
                await self.db.flush()
                return recovery

            # Determine tables to restore
            available_tables = list(backup_data.get("tables", {}).keys())
            tables = tables_to_restore or available_tables

            # Validate tables exist in backup
            invalid_tables = set(tables) - set(available_tables)
            if invalid_tables:
                recovery.fail(f"Tables not in backup: {invalid_tables}")
                await self.db.flush()
                return recovery

            total_records = 0
            restored_tables = []

            for table_name in tables:
                table_data = backup_data["tables"].get(table_name, {})
                records = table_data.get("data", [])

                if not records:
                    logger.debug(f"No records to restore for table: {table_name}")
                    continue

                try:
                    # Restore table data
                    records_restored = await self._restore_table(
                        table_name,
                        records,
                        recovery.options or {},
                        recovery.engagement_id,
                    )
                    total_records += records_restored
                    restored_tables.append(table_name)

                    logger.info(
                        "Table restored",
                        table=table_name,
                        records=records_restored,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to restore table",
                        table=table_name,
                        error=str(e),
                    )
                    # Continue with other tables

            # Complete recovery
            recovery.complete(restored_tables, total_records)

            # Create audit log entry
            audit_log = AuditLog.create(
                action=AuditAction.DATA_IMPORT,
                resource_type="recovery",
                resource_id=recovery.id,
                description=f"Recovery completed: {recovery.name}",
                user_id=recovery.created_by,
                severity=AuditSeverity.WARNING,  # Recovery is a significant action
                metadata={
                    "backup_id": str(recovery.backup_id),
                    "tables_recovered": restored_tables,
                    "records_recovered": total_records,
                },
            )
            self.db.add(audit_log)

            logger.info(
                "Recovery completed",
                recovery_id=str(recovery.id),
                tables=restored_tables,
                records=total_records,
            )

        except Exception as e:
            recovery.fail(str(e))
            logger.error(
                "Recovery failed",
                recovery_id=str(recovery.id),
                error=str(e),
                exc_info=True,
            )

            # Create audit log for failure
            audit_log = AuditLog.create(
                action=AuditAction.DATA_IMPORT,
                resource_type="recovery",
                resource_id=recovery.id,
                description=f"Recovery failed: {recovery.name}",
                user_id=recovery.created_by,
                severity=AuditSeverity.ERROR,
                metadata={"error": str(e)},
            )
            self.db.add(audit_log)

        await self.db.flush()
        return recovery

    def _load_backup_file(self, storage_path: str) -> dict[str, Any] | None:
        """
        Load and parse a backup file.

        Args:
            storage_path: Path to the backup file

        Returns:
            Parsed backup data or None if failed
        """
        if not os.path.exists(storage_path):
            logger.error("Backup file not found", path=storage_path)
            return None

        try:
            with open(storage_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to load backup file", path=storage_path, error=str(e))
            return None

    async def _create_pre_recovery_snapshot(
        self,
        recovery: Recovery,
        backup: Backup,
    ) -> Path | None:
        """
        Create a snapshot of current state before recovery.

        Args:
            recovery: Recovery operation
            backup: Source backup

        Returns:
            Path to snapshot file or None if disabled
        """
        options = recovery.options or {}
        if not options.get("create_snapshot", True):
            return None

        try:
            # Import backup service to create snapshot
            from services.backup_service import BackupService

            backup_service = BackupService(self.db, self.backup_dir)

            snapshot = await backup_service.create_backup(
                backup_type=backup.backup_type,
                name=f"pre_recovery_snapshot_{recovery.id}",
                description=f"Pre-recovery snapshot for recovery {recovery.id}",
                user_id=recovery.created_by,
                retention_days=7,  # Keep snapshots for a week
            )

            snapshot = await backup_service.execute_backup(snapshot)

            if snapshot.status == BackupStatus.COMPLETED and snapshot.storage_path:
                return Path(snapshot.storage_path)

        except Exception as e:
            logger.warning(
                "Failed to create pre-recovery snapshot",
                error=str(e),
            )

        return None

    async def _restore_table(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        options: dict[str, Any],
        engagement_id: UUID | None = None,
    ) -> int:
        """
        Restore records to a table.

        Args:
            table_name: Table to restore to
            records: Records to restore
            options: Recovery options
            engagement_id: Optional engagement filter

        Returns:
            Number of records restored

        Raises:
            ValueError: If table name is not in the allowed whitelist
        """
        if not records:
            return 0

        # Validate table name to prevent SQL injection
        _validate_table_name(table_name)

        overwrite = options.get("overwrite", False)
        merge = options.get("merge", True)

        # Handle based on strategy
        if overwrite:
            # Delete existing records (optionally filtered by engagement)
            if engagement_id and table_name not in ["audit_logs"]:
                await self._delete_engagement_records(table_name, engagement_id)
            else:
                # Don't delete audit_logs - they're immutable
                if table_name != "audit_logs":
                    await self.db.execute(text(f"DELETE FROM {table_name}"))

        # Insert records
        restored_count = 0
        for record in records:
            try:
                if merge:
                    # Use upsert (INSERT ON CONFLICT UPDATE)
                    await self._upsert_record(table_name, record)
                else:
                    # Direct insert
                    await self._insert_record(table_name, record)
                restored_count += 1
            except Exception as e:
                logger.debug(
                    "Failed to restore record",
                    table=table_name,
                    error=str(e),
                )
                # Continue with other records

        return restored_count

    async def _delete_engagement_records(
        self, table_name: str, engagement_id: UUID
    ) -> None:
        """
        Delete records for a specific engagement.

        Args:
            table_name: Table to delete from
            engagement_id: Engagement ID to filter by

        Note:
            Table name is already validated in _restore_table before this is called.
        """
        # Define allowed columns for engagement filtering
        engagement_filterable = {
            "engagements": "id",
            "workflow_runs": "engagement_id",
            "sessions": "engagement_id",
        }

        if table_name in engagement_filterable:
            column = engagement_filterable[table_name]
            await self.db.execute(
                text(f"DELETE FROM {table_name} WHERE {column} = :engagement_id"),
                {"engagement_id": str(engagement_id)},
            )

    def _sanitize_column_name(self, column: str) -> str:
        """
        Sanitize a column name to prevent SQL injection.

        Only allows alphanumeric characters and underscores.

        Args:
            column: Column name to sanitize

        Returns:
            Sanitized column name

        Raises:
            ValueError: If column name contains invalid characters
        """
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column):
            raise ValueError(f"Invalid column name: {column}")
        return column

    async def _upsert_record(self, table_name: str, record: dict[str, Any]) -> None:
        """
        Insert or update a record.

        Args:
            table_name: Table to upsert into
            record: Record data

        Note:
            Table name is already validated in _restore_table before this is called.
            Column names are sanitized to prevent SQL injection.
        """
        if not record:
            return

        # Get column names and values, sanitizing column names
        columns = [self._sanitize_column_name(col) for col in record.keys()]
        values = list(record.values())

        # Build INSERT ... ON CONFLICT UPDATE query
        placeholders = [f":val_{i}" for i in range(len(columns))]
        update_clause = ", ".join(
            f"{col} = EXCLUDED.{col}"
            for col in columns
            if col != "id"  # Don't update the primary key
        )

        query = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (id) DO UPDATE SET {update_clause}
        """

        params = {f"val_{i}": val for i, val in enumerate(values)}
        await self.db.execute(text(query), params)

    async def _insert_record(self, table_name: str, record: dict[str, Any]) -> None:
        """
        Insert a record.

        Args:
            table_name: Table to insert into
            record: Record data

        Note:
            Table name is already validated in _restore_table before this is called.
            Column names are sanitized to prevent SQL injection.
        """
        if not record:
            return

        # Get column names and values, sanitizing column names
        columns = [self._sanitize_column_name(col) for col in record.keys()]
        values = list(record.values())
        placeholders = [f":val_{i}" for i in range(len(columns))]

        query = f"""
            INSERT INTO {table_name} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
        """

        params = {f"val_{i}": val for i, val in enumerate(values)}
        await self.db.execute(text(query), params)

    async def list_recoveries(
        self,
        status: RecoveryStatus | None = None,
        backup_id: UUID | None = None,
        limit: int = 50,
    ) -> list[Recovery]:
        """
        List recoveries with optional filtering.

        Args:
            status: Optional status filter
            backup_id: Optional backup ID filter
            limit: Maximum number of recoveries to return

        Returns:
            List of Recovery records
        """
        from sqlalchemy import select

        stmt = select(Recovery).order_by(Recovery.created_at.desc()).limit(limit)

        if status:
            stmt = stmt.where(Recovery.status == status)
        if backup_id:
            stmt = stmt.where(Recovery.backup_id == backup_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recovery(self, recovery_id: UUID) -> Recovery | None:
        """
        Get a recovery by ID.

        Args:
            recovery_id: Recovery ID to retrieve

        Returns:
            Recovery record or None if not found
        """
        from sqlalchemy import select

        stmt = select(Recovery).where(Recovery.id == recovery_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def rollback_recovery(
        self,
        recovery_id: UUID,
        user_id: UUID | None = None,
    ) -> Recovery | None:
        """
        Rollback a recovery operation using its pre-recovery snapshot.

        Args:
            recovery_id: Recovery ID to rollback
            user_id: User performing the rollback

        Returns:
            Updated Recovery record or None if failed
        """
        recovery = await self.get_recovery(recovery_id)
        if not recovery:
            return None

        if recovery.status != RecoveryStatus.COMPLETED:
            raise ValueError(
                f"Can only rollback completed recoveries, current status: {recovery.status.value}"
            )

        if not recovery.pre_recovery_snapshot:
            raise ValueError("No pre-recovery snapshot available for rollback")

        # Create a new recovery from the snapshot
        # First, find the snapshot backup
        from sqlalchemy import select

        stmt = select(Backup).where(
            Backup.storage_path == recovery.pre_recovery_snapshot
        )
        result = await self.db.execute(stmt)
        snapshot_backup = result.scalar_one_or_none()

        if not snapshot_backup:
            raise ValueError("Pre-recovery snapshot backup not found")

        # Create rollback recovery
        rollback_recovery = await self.create_recovery(
            backup_id=snapshot_backup.id,
            name=f"rollback_{recovery.name}",
            description=f"Rollback of recovery {recovery.id}",
            user_id=user_id,
            options={"overwrite": True, "create_snapshot": False},
        )

        # Execute rollback
        rollback_recovery = await self.execute_recovery(rollback_recovery)

        if rollback_recovery.status == RecoveryStatus.COMPLETED:
            recovery.rollback()
            await self.db.flush()

            # Create audit log
            audit_log = AuditLog.create(
                action=AuditAction.DATA_IMPORT,
                resource_type="recovery",
                resource_id=recovery.id,
                description=f"Recovery rolled back: {recovery.name}",
                user_id=user_id,
                severity=AuditSeverity.WARNING,
                metadata={
                    "rollback_recovery_id": str(rollback_recovery.id),
                },
            )
            self.db.add(audit_log)

        return recovery

    async def validate_backup_for_recovery(
        self, backup_id: UUID
    ) -> dict[str, Any]:
        """
        Validate that a backup can be used for recovery.

        Args:
            backup_id: Backup ID to validate

        Returns:
            Validation result dictionary
        """
        backup = await self.get_backup(backup_id)
        if not backup:
            return {"valid": False, "error": "Backup not found"}

        if backup.status != BackupStatus.COMPLETED:
            return {
                "valid": False,
                "error": f"Backup status is {backup.status.value}, must be completed",
            }

        if not backup.storage_path or not os.path.exists(backup.storage_path):
            return {"valid": False, "error": "Backup file not found"}

        # Load and validate backup file
        backup_data = self._load_backup_file(backup.storage_path)
        if not backup_data:
            return {"valid": False, "error": "Failed to load backup file"}

        tables = backup_data.get("tables", {})
        table_info = {
            name: {"record_count": data.get("record_count", 0)}
            for name, data in tables.items()
        }

        return {
            "valid": True,
            "backup_id": str(backup.id),
            "backup_name": backup.name,
            "backup_type": backup.backup_type.value,
            "tables": table_info,
            "total_records": sum(t["record_count"] for t in table_info.values()),
            "created_at": backup.created_at.isoformat() if backup.created_at else None,
        }


async def get_recovery_service(db: AsyncSession) -> RecoveryService:
    """
    FastAPI dependency for getting a RecoveryService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured RecoveryService instance
    """
    return RecoveryService(db)
