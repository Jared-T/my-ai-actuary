"""
CLI Tasks API endpoints.

Provides REST endpoints for:
- Submitting and managing CLI tasks
- Monitoring task execution progress
- Retrieving task results
- Batch processing operations
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.logging import get_logger
from models.cli_task import CLITaskPriority, CLITaskStatus, CLITaskType
from services.cli_task_service import CLITaskService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cli-tasks", tags=["CLI Tasks"])


# Request/Response Models
class SubmitTaskRequest(BaseModel):
    """Request model for submitting a CLI task."""

    name: str = Field(
        description="Human-readable name for the task",
        min_length=1,
        max_length=255,
    )
    command: str = Field(
        description="The CLI command to execute",
        min_length=1,
    )
    task_type: CLITaskType = Field(
        default=CLITaskType.SHELL_COMMAND,
        description="Type of CLI task",
    )
    description: str | None = Field(
        default=None,
        description="Optional task description",
    )
    input_data: dict[str, Any] | None = Field(
        default=None,
        description="Optional input parameters",
    )
    input_file_path: str | None = Field(
        default=None,
        description="Optional path to input file",
    )
    working_directory: str | None = Field(
        default=None,
        description="Optional working directory",
    )
    environment_vars: dict[str, str] | None = Field(
        default=None,
        description="Optional environment variables",
    )
    timeout_seconds: int = Field(
        default=3600,
        ge=1,
        le=86400,
        description="Maximum execution time in seconds (max: 24 hours)",
    )
    priority: CLITaskPriority = Field(
        default=CLITaskPriority.NORMAL,
        description="Task execution priority",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Optional associated engagement ID",
    )


class TaskResponse(BaseModel):
    """Response model for task information."""

    id: UUID
    name: str
    task_type: str
    status: str
    priority: str
    command: str
    description: str | None
    progress_percentage: float
    progress_message: str | None
    input_data: dict | None
    output_data: dict | None
    input_file_path: str | None
    output_file_path: str | None
    exit_code: int | None
    error_message: str | None
    retry_count: int
    max_retries: int
    timeout_seconds: int
    engagement_id: UUID | None
    parent_task_id: UUID | None
    trace_id: str | None
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    """Response model for task status check."""

    id: UUID
    name: str
    task_type: str
    status: str
    progress_percentage: float
    progress_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    error_message: str | None
    is_running: bool
    is_finished: bool


class TaskListResponse(BaseModel):
    """Response model for listing tasks."""

    tasks: list[TaskResponse]
    total: int


class BatchSubmitRequest(BaseModel):
    """Request model for submitting a batch of tasks."""

    name: str = Field(
        description="Name for the batch operation",
        min_length=1,
        max_length=255,
    )
    commands: list[str] = Field(
        description="List of commands to execute",
        min_length=1,
        max_length=100,
    )
    task_type: CLITaskType = Field(
        default=CLITaskType.SHELL_COMMAND,
        description="Type for all tasks in the batch",
    )
    description: str | None = Field(
        default=None,
        description="Optional batch description",
    )
    engagement_id: UUID | None = Field(
        default=None,
        description="Optional associated engagement ID",
    )


class BatchStatusResponse(BaseModel):
    """Response model for batch status."""

    parent_task_id: UUID
    name: str
    total_tasks: int
    completed: int
    failed: int
    running: int
    pending: int
    progress_percentage: float
    is_complete: bool
    has_failures: bool


def _task_to_response(task: Any) -> TaskResponse:
    """Convert a CLITask model to a TaskResponse."""
    return TaskResponse(
        id=task.id,
        name=task.name,
        task_type=task.task_type.value,
        status=task.status.value,
        priority=task.priority.value,
        command=task.command,
        description=task.description,
        progress_percentage=task.progress_percentage,
        progress_message=task.progress_message,
        input_data=task.input_data,
        output_data=task.output_data,
        input_file_path=task.input_file_path,
        output_file_path=task.output_file_path,
        exit_code=task.exit_code,
        error_message=task.error_message,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        timeout_seconds=task.timeout_seconds,
        engagement_id=task.engagement_id,
        parent_task_id=task.parent_task_id,
        trace_id=task.trace_id,
        created_at=task.created_at,
        queued_at=task.queued_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


def _task_to_status_response(task: Any) -> TaskStatusResponse:
    """Convert a CLITask model to a TaskStatusResponse."""
    return TaskStatusResponse(
        id=task.id,
        name=task.name,
        task_type=task.task_type.value,
        status=task.status.value,
        progress_percentage=task.progress_percentage,
        progress_message=task.progress_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        duration_seconds=task.duration_seconds,
        error_message=task.error_message,
        is_running=task.is_running,
        is_finished=task.is_finished,
    )


# Task Endpoints
@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new CLI task",
    description="Submit a CLI task for execution. Use execute=true to run immediately.",
)
async def submit_task(
    request: SubmitTaskRequest,
    execute: bool = Query(default=False, description="Execute task immediately"),
    background: bool = Query(default=True, description="Execute in background (non-blocking)"),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """
    Submit a new CLI task.

    Creates a task record and optionally executes it immediately.
    By default, tasks run in the background - use background=false to wait for completion.
    """
    service = CLITaskService(db)

    try:
        task = await service.submit_task(
            name=request.name,
            task_type=request.task_type,
            command=request.command,
            description=request.description,
            input_data=request.input_data,
            input_file_path=request.input_file_path,
            working_directory=request.working_directory,
            environment_vars=request.environment_vars,
            timeout_seconds=request.timeout_seconds,
            priority=request.priority,
            max_retries=request.max_retries,
            engagement_id=request.engagement_id,
        )

        if execute:
            if background:
                task = await service.execute_task_background(task)
            else:
                task = await service.execute_task(task)

        await db.commit()

        return _task_to_response(task)

    except Exception as e:
        logger.error("Failed to submit task", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit task: {str(e)}",
        )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List CLI tasks",
    description="List all CLI tasks with optional filtering",
)
async def list_tasks(
    status_filter: CLITaskStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    task_type: CLITaskType | None = Query(
        default=None, description="Filter by task type"
    ),
    engagement_id: UUID | None = Query(
        default=None, description="Filter by engagement ID"
    ),
    parent_task_id: UUID | None = Query(
        default=None, description="Filter by parent task ID (for batch tasks)"
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """
    List CLI tasks with optional filtering.

    Returns a list of tasks ordered by creation date (newest first).
    """
    service = CLITaskService(db)

    tasks = await service.list_tasks(
        status=status_filter,
        task_type=task_type,
        engagement_id=engagement_id,
        parent_task_id=parent_task_id,
        limit=limit,
    )

    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Get detailed information about a specific CLI task",
)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Get task details by ID."""
    service = CLITaskService(db)

    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return _task_to_response(task)


@router.get(
    "/{task_id}/status",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Get the current status and progress of a task",
)
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TaskStatusResponse:
    """Get task status by ID."""
    service = CLITaskService(db)

    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return _task_to_status_response(task)


@router.post(
    "/{task_id}/execute",
    response_model=TaskResponse,
    summary="Execute a pending task",
    description="Execute a task that was submitted without immediate execution",
)
async def execute_task(
    task_id: UUID,
    background: bool = Query(default=True, description="Execute in background"),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Execute a pending task."""
    service = CLITaskService(db)

    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    if task.status not in (CLITaskStatus.PENDING, CLITaskStatus.QUEUED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute task in status: {task.status.value}",
        )

    try:
        if background:
            task = await service.execute_task_background(task)
        else:
            task = await service.execute_task(task)

        await db.commit()

        return _task_to_response(task)

    except Exception as e:
        logger.error("Failed to execute task", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute task: {str(e)}",
        )


@router.post(
    "/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Cancel a running task",
    description="Cancel a task that is currently running",
)
async def cancel_task(
    task_id: UUID,
    reason: str | None = Query(default=None, description="Cancellation reason"),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Cancel a running task."""
    service = CLITaskService(db)

    try:
        task = await service.cancel_task(task_id, reason=reason)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        await db.commit()

        return _task_to_response(task)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to cancel task", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.post(
    "/{task_id}/retry",
    response_model=TaskResponse,
    summary="Retry a failed task",
    description="Retry a task that has failed or timed out",
)
async def retry_task(
    task_id: UUID,
    execute: bool = Query(default=True, description="Execute immediately after retry"),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Retry a failed task."""
    service = CLITaskService(db)

    try:
        task = await service.retry_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}",
            )

        if execute:
            task = await service.execute_task_background(task)

        await db.commit()

        return _task_to_response(task)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to retry task", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry task: {str(e)}",
        )


# Batch Endpoints
batch_router = APIRouter(prefix="/api/cli-tasks/batch", tags=["CLI Task Batches"])


@batch_router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a batch of tasks",
    description="Submit multiple commands as a single batch operation",
)
async def submit_batch(
    request: BatchSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """
    Submit a batch of CLI tasks.

    Creates a parent task and child tasks for each command.
    Use get_batch_status to monitor overall progress.
    """
    service = CLITaskService(db)

    try:
        parent_task = await service.submit_batch(
            name=request.name,
            task_type=request.task_type,
            commands=request.commands,
            description=request.description,
            engagement_id=request.engagement_id,
        )

        await db.commit()

        return _task_to_response(parent_task)

    except Exception as e:
        logger.error("Failed to submit batch", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit batch: {str(e)}",
        )


@batch_router.get(
    "/{parent_task_id}/status",
    response_model=BatchStatusResponse,
    summary="Get batch status",
    description="Get the status and progress of a batch operation",
)
async def get_batch_status(
    parent_task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BatchStatusResponse:
    """Get batch operation status."""
    service = CLITaskService(db)

    status_data = await service.get_batch_status(parent_task_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch task not found: {parent_task_id}",
        )

    return BatchStatusResponse(
        parent_task_id=UUID(status_data["parent_task_id"]),
        name=status_data["name"],
        total_tasks=status_data["total_tasks"],
        completed=status_data["completed"],
        failed=status_data["failed"],
        running=status_data["running"],
        pending=status_data["pending"],
        progress_percentage=status_data["progress_percentage"],
        is_complete=status_data["is_complete"],
        has_failures=status_data["has_failures"],
    )


@batch_router.get(
    "/{parent_task_id}/tasks",
    response_model=TaskListResponse,
    summary="List batch tasks",
    description="List all tasks in a batch operation",
)
async def list_batch_tasks(
    parent_task_id: UUID,
    status_filter: CLITaskStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """List all tasks in a batch."""
    service = CLITaskService(db)

    tasks = await service.list_tasks(
        parent_task_id=parent_task_id,
        status=status_filter,
        limit=limit,
    )

    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )
