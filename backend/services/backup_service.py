"""
Backup service for automated backup strategy and recovery procedures.

Provides functionality for:
- Creating full and incremental database backups
- Backing up audit trails and artefacts
- Engagement-level selective backups
- Backup scheduling and retention management
"""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from models.audit import AuditAction, AuditLog, AuditSeverity
from models.backup import Backup, BackupStatus, BackupType

logger = get_logger(__name__)

# Allowed tables for backup operations - whitelist to prevent SQL injection
ALLOWED_BACKUP_TABLES = frozenset({
    "sessions",
    "chat_messages",
    "engagements",
    "workflow_runs",
    "artefacts",
    "approvals",
    "audit_logs",
    "backups",
    "recoveries",
})


def get_backup_dir() -> Path:
    """Get the backup directory from settings."""
    return Path(settings.backup_dir)


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


class BackupService:
    """
    Service for managing backup operations.

    Provides methods for creating, listing, and managing backups
    of critical project data and audit trails.
    """

    def __init__(self, db: AsyncSession, backup_dir: Path | None = None) -> None:
        """
        Initialize the backup service.

        Args:
            db: Database session for operations
            backup_dir: Optional custom backup directory
        """
        self.db = db
        self.backup_dir = backup_dir or get_backup_dir()
        self._ensure_backup_dir()

    def _ensure_backup_dir(self) -> None:
        """Ensure backup directory exists."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Backup directory ready", path=str(self.backup_dir))

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _serialize_row(self, columns: list[str], row: tuple) -> dict[str, Any]:
        """
        Serialize a database row to a JSON-compatible dictionary.

        Args:
            columns: Column names
            row: Row data tuple

        Returns:
            JSON-serializable dictionary
        """
        row_dict = {}
        for col, val in zip(columns, row):
            if isinstance(val, datetime):
                row_dict[col] = val.isoformat()
            elif isinstance(val, UUID):
                row_dict[col] = str(val)
            elif hasattr(val, "value"):  # Enum
                row_dict[col] = val.value
            else:
                row_dict[col] = val
        return row_dict

    async def _get_table_data(self, table_name: str) -> list[dict[str, Any]]:
        """
        Export data from a table as a list of dictionaries.

        Args:
            table_name: Name of the table to export

        Returns:
            List of row dictionaries

        Raises:
            ValueError: If table name is not in the allowed whitelist
        """
        _validate_table_name(table_name)
        result = await self.db.execute(text(f"SELECT * FROM {table_name}"))
        columns = list(result.keys())
        return [self._serialize_row(columns, row) for row in result.fetchall()]

    async def _get_table_count(self, table_name: str) -> int:
        """Get record count for a table."""
        _validate_table_name(table_name)
        result = await self.db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0

    async def create_backup(
        self,
        backup_type: BackupType,
        name: str | None = None,
        description: str | None = None,
        engagement_id: UUID | None = None,
        user_id: UUID | None = None,
        retention_days: int = 30,
    ) -> Backup:
        """
        Create a new backup.

        Args:
            backup_type: Type of backup to create
            name: Optional custom name for the backup
            description: Optional description
            engagement_id: Optional engagement ID for selective backup
            user_id: User initiating the backup
            retention_days: Number of days to retain the backup

        Returns:
            Created Backup record
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = name or f"{backup_type.value}_backup_{timestamp}"

        # Create backup record
        backup = Backup(
            name=backup_name,
            description=description,
            backup_type=backup_type,
            status=BackupStatus.PENDING,
            storage_provider="local",
            engagement_id=engagement_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=retention_days),
            created_by=user_id,
            updated_by=user_id,
            extra_metadata={
                "environment": settings.environment,
                "app_version": settings.app_version,
                "initiated_by": str(user_id) if user_id else "system",
            },
        )
        self.db.add(backup)
        await self.db.flush()

        logger.info(
            "Backup created",
            backup_id=str(backup.id),
            backup_type=backup_type.value,
            name=backup_name,
        )

        return backup

    async def execute_backup(self, backup: Backup) -> Backup:
        """
        Execute a backup operation.

        Args:
            backup: Backup record to execute

        Returns:
            Updated Backup record with results
        """
        backup.start()
        await self.db.flush()

        try:
            # Determine tables to backup based on type
            tables_to_backup = self._get_tables_for_backup_type(backup.backup_type)
            backup.tables_included = tables_to_backup

            # Prepare backup data
            backup_data: dict[str, Any] = {
                "backup_id": str(backup.id),
                "backup_type": backup.backup_type.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "environment": settings.environment,
                "app_version": settings.app_version,
                "tables": {},
            }

            total_records = 0

            for table_name in tables_to_backup:
                try:
                    # Get data with optional engagement filter
                    if backup.engagement_id and table_name not in ["audit_logs"]:
                        data = await self._get_engagement_filtered_data(
                            table_name, backup.engagement_id
                        )
                    else:
                        data = await self._get_table_data(table_name)

                    backup_data["tables"][table_name] = {
                        "record_count": len(data),
                        "data": data,
                    }
                    total_records += len(data)

                    logger.debug(
                        "Table exported",
                        table=table_name,
                        records=len(data),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to export table",
                        table=table_name,
                        error=str(e),
                    )
                    backup_data["tables"][table_name] = {
                        "record_count": 0,
                        "error": str(e),
                        "data": [],
                    }

            # Write backup file
            backup_filename = f"{backup.id}_{backup.backup_type.value}.json"
            backup_path = self.backup_dir / backup_filename

            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            # Calculate checksum and file size
            file_size = backup_path.stat().st_size
            checksum = self._calculate_checksum(backup_path)

            # Complete backup
            backup.complete(
                storage_path=str(backup_path),
                file_size_bytes=file_size,
                record_count=total_records,
                checksum=checksum,
            )

            # Create audit log entry
            audit_log = AuditLog.create(
                action=AuditAction.DATA_EXPORT,
                resource_type="backup",
                resource_id=backup.id,
                description=f"Backup completed: {backup.name}",
                user_id=backup.created_by,
                severity=AuditSeverity.INFO,
                metadata={
                    "backup_type": backup.backup_type.value,
                    "tables": tables_to_backup,
                    "record_count": total_records,
                    "file_size_bytes": file_size,
                },
            )
            self.db.add(audit_log)

            logger.info(
                "Backup completed",
                backup_id=str(backup.id),
                records=total_records,
                file_size=file_size,
            )

        except Exception as e:
            backup.fail(str(e))
            logger.error(
                "Backup failed",
                backup_id=str(backup.id),
                error=str(e),
                exc_info=True,
            )

            # Create audit log for failure
            audit_log = AuditLog.create(
                action=AuditAction.DATA_EXPORT,
                resource_type="backup",
                resource_id=backup.id,
                description=f"Backup failed: {backup.name}",
                user_id=backup.created_by,
                severity=AuditSeverity.ERROR,
                metadata={"error": str(e)},
            )
            self.db.add(audit_log)

        await self.db.flush()
        return backup

    def _get_tables_for_backup_type(self, backup_type: BackupType) -> list[str]:
        """Get list of tables to backup based on backup type."""
        # Core tables for full backups
        core_tables = [
            "sessions",
            "chat_messages",
            "engagements",
            "workflow_runs",
            "artefacts",
            "approvals",
        ]

        audit_tables = ["audit_logs"]

        backup_tables = ["backups", "recoveries"]

        if backup_type == BackupType.FULL:
            return core_tables + audit_tables + backup_tables
        elif backup_type == BackupType.AUDIT_LOGS:
            return audit_tables
        elif backup_type == BackupType.ENGAGEMENT:
            return core_tables  # Will be filtered by engagement_id
        elif backup_type == BackupType.ARTEFACTS:
            return ["artefacts"]
        elif backup_type in (BackupType.INCREMENTAL, BackupType.DIFFERENTIAL):
            return core_tables + audit_tables
        else:
            return core_tables

    async def _get_engagement_filtered_data(
        self, table_name: str, engagement_id: UUID
    ) -> list[dict[str, Any]]:
        """
        Get data from a table filtered by engagement.

        Args:
            table_name: Table to query
            engagement_id: Engagement ID to filter by

        Returns:
            Filtered list of row dictionaries

        Raises:
            ValueError: If table name is not in the allowed whitelist
        """
        # Validate table name first to prevent SQL injection
        _validate_table_name(table_name)

        # Tables that can be filtered by engagement_id
        engagement_filterable = {
            "engagements": "id",
            "workflow_runs": "engagement_id",
            "artefacts": "workflow_run_id",  # Need to join through workflow_runs
            "approvals": "workflow_run_id",  # Need to join through workflow_runs
            "sessions": "engagement_id",
        }

        if table_name not in engagement_filterable:
            return await self._get_table_data(table_name)

        if table_name == "engagements":
            query = f"SELECT * FROM {table_name} WHERE id = :engagement_id"
        elif table_name in ("artefacts", "approvals"):
            # Join through workflow_runs (workflow_runs is also validated)
            query = f"""
                SELECT t.* FROM {table_name} t
                INNER JOIN workflow_runs w ON t.workflow_run_id = w.id
                WHERE w.engagement_id = :engagement_id
            """
        else:
            query = f"SELECT * FROM {table_name} WHERE engagement_id = :engagement_id"

        result = await self.db.execute(
            text(query), {"engagement_id": str(engagement_id)}
        )
        columns = list(result.keys())
        return [self._serialize_row(columns, row) for row in result.fetchall()]

    async def list_backups(
        self,
        status: BackupStatus | None = None,
        backup_type: BackupType | None = None,
        limit: int = 50,
    ) -> list[Backup]:
        """
        List backups with optional filtering.

        Args:
            status: Optional status filter
            backup_type: Optional type filter
            limit: Maximum number of backups to return

        Returns:
            List of Backup records
        """
        stmt = select(Backup).order_by(Backup.created_at.desc()).limit(limit)

        if status:
            stmt = stmt.where(Backup.status == status)
        if backup_type:
            stmt = stmt.where(Backup.backup_type == backup_type)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_backup(self, backup_id: UUID) -> Backup | None:
        """
        Get a backup by ID.

        Args:
            backup_id: Backup ID to retrieve

        Returns:
            Backup record or None if not found
        """
        stmt = select(Backup).where(Backup.id == backup_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_backup(self, backup_id: UUID, user_id: UUID | None = None) -> bool:
        """
        Delete a backup record and its file.

        Args:
            backup_id: Backup ID to delete
            user_id: User performing the deletion

        Returns:
            True if deleted, False if not found
        """
        backup = await self.get_backup(backup_id)
        if not backup:
            return False

        # Delete backup file if it exists
        if backup.storage_path and os.path.exists(backup.storage_path):
            try:
                os.remove(backup.storage_path)
                logger.info("Backup file deleted", path=backup.storage_path)
            except OSError as e:
                logger.warning(
                    "Failed to delete backup file",
                    path=backup.storage_path,
                    error=str(e),
                )

        # Create audit log
        audit_log = AuditLog.create(
            action=AuditAction.DATA_EXPORT,
            resource_type="backup",
            resource_id=backup.id,
            description=f"Backup deleted: {backup.name}",
            user_id=user_id,
            severity=AuditSeverity.WARNING,
            old_value={
                "backup_type": backup.backup_type.value,
                "storage_path": backup.storage_path,
            },
        )
        self.db.add(audit_log)

        # Delete the record
        await self.db.delete(backup)
        await self.db.flush()

        logger.info("Backup deleted", backup_id=str(backup_id))
        return True

    async def cleanup_expired_backups(self) -> int:
        """
        Delete backups that have passed their expiration date.

        Returns:
            Number of backups deleted
        """
        now = datetime.now(timezone.utc)
        stmt = select(Backup).where(
            Backup.expires_at < now,
            Backup.status == BackupStatus.COMPLETED,
        )
        result = await self.db.execute(stmt)
        expired_backups = list(result.scalars().all())

        deleted_count = 0
        for backup in expired_backups:
            if await self.delete_backup(backup.id):
                deleted_count += 1

        logger.info("Expired backups cleaned up", count=deleted_count)
        return deleted_count

    async def verify_backup_integrity(self, backup_id: UUID) -> dict[str, Any]:
        """
        Verify the integrity of a backup file.

        Args:
            backup_id: Backup ID to verify

        Returns:
            Verification result dictionary
        """
        backup = await self.get_backup(backup_id)
        if not backup:
            return {"valid": False, "error": "Backup not found"}

        if not backup.storage_path or not os.path.exists(backup.storage_path):
            return {"valid": False, "error": "Backup file not found"}

        try:
            # Calculate current checksum
            current_checksum = self._calculate_checksum(Path(backup.storage_path))

            if backup.checksum and current_checksum != backup.checksum:
                return {
                    "valid": False,
                    "error": "Checksum mismatch",
                    "expected": backup.checksum,
                    "actual": current_checksum,
                }

            # Verify JSON structure
            with open(backup.storage_path, "r") as f:
                data = json.load(f)

            return {
                "valid": True,
                "checksum": current_checksum,
                "tables": list(data.get("tables", {}).keys()),
                "total_records": sum(
                    t.get("record_count", 0) for t in data.get("tables", {}).values()
                ),
            }

        except json.JSONDecodeError as e:
            return {"valid": False, "error": f"Invalid JSON: {str(e)}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}


async def get_backup_service(db: AsyncSession) -> BackupService:
    """
    FastAPI dependency for getting a BackupService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured BackupService instance
    """
    return BackupService(db)
