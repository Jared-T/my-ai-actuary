"""
Backup and recovery API endpoints.

Provides REST endpoints for:
- Creating and managing backups
- Initiating and monitoring recovery operations
- Backup verification and integrity checks
- Cleanup of expired backups
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logging import get_logger
from models.backup import BackupStatus, BackupType, RecoveryStatus
from services.backup_service import BackupService, get_backup_service
from services.recovery_service import RecoveryService, get_recovery_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backups", tags=["Backups"])


# Request/Response Models
class CreateBackupRequest(BaseModel):
    """Request model for creating a backup."""

    backup_type: BackupType = Field(
        default=BackupType.FULL,
        description="Type of backup to create",
    )
    name: str | None = Field(
        default=None,
        description="Optional custom name for the backup",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of the backup",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Optional engagement ID for selective backup",
    )
    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days to retain the backup",
    )


class BackupResponse(BaseModel):
    """Response model for backup information."""

    id: UUID
    name: str
    backup_type: str
    status: str
    storage_path: str | None
    file_size_bytes: int | None
    record_count: int | None
    checksum: str | None
    tables_included: list[str] | None
    engagement_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None
    error_message: str | None

    class Config:
        from_attributes = True


class CreateRecoveryRequest(BaseModel):
    """Request model for creating a recovery operation."""

    backup_id: UUID = Field(description="Source backup ID for recovery")
    name: str | None = Field(
        default=None,
        description="Optional custom name for the recovery",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of the recovery",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Target engagement for selective recovery",
    )
    tables_to_restore: list[str] | None = Field(
        default=None,
        description="Specific tables to restore (all if not specified)",
    )
    overwrite: bool = Field(
        default=False,
        description="Whether to overwrite existing data",
    )
    create_snapshot: bool = Field(
        default=True,
        description="Whether to create pre-recovery snapshot for rollback",
    )


class RecoveryResponse(BaseModel):
    """Response model for recovery information."""

    id: UUID
    name: str
    backup_id: UUID
    status: str
    tables_recovered: list[str] | None
    records_recovered: int | None
    engagement_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    pre_recovery_snapshot: str | None

    class Config:
        from_attributes = True


class BackupListResponse(BaseModel):
    """Response model for listing backups."""

    backups: list[BackupResponse]
    total: int


class RecoveryListResponse(BaseModel):
    """Response model for listing recoveries."""

    recoveries: list[RecoveryResponse]
    total: int


class VerificationResponse(BaseModel):
    """Response model for backup verification."""

    valid: bool
    checksum: str | None = None
    tables: list[str] | None = None
    total_records: int | None = None
    error: str | None = None


def _backup_to_response(backup) -> BackupResponse:
    """Convert a Backup model to a BackupResponse."""
    return BackupResponse(
        id=backup.id,
        name=backup.name,
        backup_type=backup.backup_type.value,
        status=backup.status.value,
        storage_path=backup.storage_path,
        file_size_bytes=backup.file_size_bytes,
        record_count=backup.record_count,
        checksum=backup.checksum,
        tables_included=backup.tables_included,
        engagement_id=backup.engagement_id,
        created_at=backup.created_at,
        started_at=backup.started_at,
        completed_at=backup.completed_at,
        expires_at=backup.expires_at,
        error_message=backup.error_message,
    )


def _recovery_to_response(recovery) -> RecoveryResponse:
    """Convert a Recovery model to a RecoveryResponse."""
    return RecoveryResponse(
        id=recovery.id,
        name=recovery.name,
        backup_id=recovery.backup_id,
        status=recovery.status.value,
        tables_recovered=recovery.tables_recovered,
        records_recovered=recovery.records_recovered,
        engagement_id=recovery.engagement_id,
        created_at=recovery.created_at,
        started_at=recovery.started_at,
        completed_at=recovery.completed_at,
        error_message=recovery.error_message,
        pre_recovery_snapshot=recovery.pre_recovery_snapshot,
    )


# Backup Endpoints
@router.post(
    "",
    response_model=BackupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new backup",
    description="Create and optionally execute a new backup operation",
)
async def create_backup(
    request: CreateBackupRequest,
    execute: bool = Query(default=True, description="Execute backup immediately"),
    db: AsyncSession = Depends(get_db),
) -> BackupResponse:
    """
    Create a new backup.

    Creates a backup record and optionally executes it immediately.
    Supports various backup types including full, incremental, and engagement-specific.
    """
    backup_service = BackupService(db)

    try:
        backup = await backup_service.create_backup(
            backup_type=request.backup_type,
            name=request.name,
            description=request.description,
            engagement_id=request.engagement_id,
            retention_days=request.retention_days,
        )

        if execute:
            backup = await backup_service.execute_backup(backup)

        await db.commit()

        return _backup_to_response(backup)

    except Exception as e:
        logger.error("Failed to create backup", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create backup: {str(e)}",
        )


@router.get(
    "",
    response_model=BackupListResponse,
    summary="List backups",
    description="List all backups with optional filtering",
)
async def list_backups(
    status_filter: BackupStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    backup_type: BackupType | None = Query(
        default=None, description="Filter by backup type"
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> BackupListResponse:
    """
    List backups with optional filtering.

    Returns a list of backups ordered by creation date (newest first).
    """
    backup_service = BackupService(db)

    backups = await backup_service.list_backups(
        status=status_filter,
        backup_type=backup_type,
        limit=limit,
    )

    return BackupListResponse(
        backups=[_backup_to_response(b) for b in backups],
        total=len(backups),
    )


@router.get(
    "/{backup_id}",
    response_model=BackupResponse,
    summary="Get backup details",
    description="Get detailed information about a specific backup",
)
async def get_backup(
    backup_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BackupResponse:
    """Get backup details by ID."""
    backup_service = BackupService(db)

    backup = await backup_service.get_backup(backup_id)
    if not backup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup not found: {backup_id}",
        )

    return _backup_to_response(backup)


@router.post(
    "/{backup_id}/verify",
    response_model=VerificationResponse,
    summary="Verify backup integrity",
    description="Verify the integrity of a backup file",
)
async def verify_backup(
    backup_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VerificationResponse:
    """Verify backup file integrity using checksum."""
    backup_service = BackupService(db)

    result = await backup_service.verify_backup_integrity(backup_id)

    return VerificationResponse(
        valid=result.get("valid", False),
        checksum=result.get("checksum"),
        tables=result.get("tables"),
        total_records=result.get("total_records"),
        error=result.get("error"),
    )


@router.delete(
    "/{backup_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a backup",
    description="Delete a backup and its associated file",
)
async def delete_backup(
    backup_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a backup by ID."""
    backup_service = BackupService(db)

    deleted = await backup_service.delete_backup(backup_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup not found: {backup_id}",
        )

    await db.commit()


@router.post(
    "/cleanup",
    summary="Cleanup expired backups",
    description="Delete all backups that have passed their expiration date",
)
async def cleanup_expired_backups(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cleanup expired backups."""
    backup_service = BackupService(db)

    deleted_count = await backup_service.cleanup_expired_backups()
    await db.commit()

    return {
        "message": f"Cleaned up {deleted_count} expired backups",
        "deleted_count": deleted_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Recovery Endpoints
recovery_router = APIRouter(prefix="/api/recoveries", tags=["Recoveries"])


@recovery_router.post(
    "",
    response_model=RecoveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recovery",
    description="Create and optionally execute a recovery operation",
)
async def create_recovery(
    request: CreateRecoveryRequest,
    execute: bool = Query(default=True, description="Execute recovery immediately"),
    db: AsyncSession = Depends(get_db),
) -> RecoveryResponse:
    """
    Create a new recovery operation.

    Creates a recovery record and optionally executes it immediately.
    Supports selective table restoration and pre-recovery snapshots.
    """
    recovery_service = RecoveryService(db)

    try:
        # First validate the backup
        validation = await recovery_service.validate_backup_for_recovery(
            request.backup_id
        )
        if not validation.get("valid"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid backup for recovery: {validation.get('error')}",
            )

        recovery = await recovery_service.create_recovery(
            backup_id=request.backup_id,
            name=request.name,
            description=request.description,
            engagement_id=request.engagement_id,
            options={
                "overwrite": request.overwrite,
                "create_snapshot": request.create_snapshot,
                "merge": not request.overwrite,
            },
        )

        if execute:
            recovery = await recovery_service.execute_recovery(
                recovery,
                tables_to_restore=request.tables_to_restore,
            )

        await db.commit()

        return _recovery_to_response(recovery)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to create recovery", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create recovery: {str(e)}",
        )


@recovery_router.get(
    "",
    response_model=RecoveryListResponse,
    summary="List recoveries",
    description="List all recovery operations with optional filtering",
)
async def list_recoveries(
    status_filter: RecoveryStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    backup_id: UUID | None = Query(
        default=None, description="Filter by source backup ID"
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> RecoveryListResponse:
    """List recoveries with optional filtering."""
    recovery_service = RecoveryService(db)

    recoveries = await recovery_service.list_recoveries(
        status=status_filter,
        backup_id=backup_id,
        limit=limit,
    )

    return RecoveryListResponse(
        recoveries=[_recovery_to_response(r) for r in recoveries],
        total=len(recoveries),
    )


@recovery_router.get(
    "/{recovery_id}",
    response_model=RecoveryResponse,
    summary="Get recovery details",
    description="Get detailed information about a specific recovery",
)
async def get_recovery(
    recovery_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RecoveryResponse:
    """Get recovery details by ID."""
    recovery_service = RecoveryService(db)

    recovery = await recovery_service.get_recovery(recovery_id)
    if not recovery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery not found: {recovery_id}",
        )

    return _recovery_to_response(recovery)


@recovery_router.post(
    "/{recovery_id}/validate",
    summary="Validate backup for recovery",
    description="Validate that a backup can be used for recovery",
)
async def validate_backup_for_recovery(
    recovery_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Validate backup for a recovery operation.

    Checks that the source backup exists, is complete, and can be parsed.
    """
    recovery_service = RecoveryService(db)

    recovery = await recovery_service.get_recovery(recovery_id)
    if not recovery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery not found: {recovery_id}",
        )

    return await recovery_service.validate_backup_for_recovery(recovery.backup_id)


@recovery_router.post(
    "/{recovery_id}/rollback",
    response_model=RecoveryResponse,
    summary="Rollback a recovery",
    description="Rollback a completed recovery using its pre-recovery snapshot",
)
async def rollback_recovery(
    recovery_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RecoveryResponse:
    """
    Rollback a recovery operation.

    Uses the pre-recovery snapshot to restore data to the state
    before the recovery was executed.
    """
    recovery_service = RecoveryService(db)

    try:
        recovery = await recovery_service.rollback_recovery(recovery_id)
        if not recovery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recovery not found: {recovery_id}",
            )

        await db.commit()

        return _recovery_to_response(recovery)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to rollback recovery", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback recovery: {str(e)}",
        )
