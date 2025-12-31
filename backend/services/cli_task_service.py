"""
CLI Task service for Codex CLI integration.

Provides functionality for:
- Submitting and managing CLI tasks
- Executing long-running processes
- Polling task status and progress
- Handling batch processing operations

Security Note:
    This service executes shell commands. Commands should be validated
    before execution in production environments. Consider implementing
    command allowlists or sandboxing for untrusted inputs.
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from models.audit import AuditAction, AuditLog, AuditSeverity
from models.cli_task import (
    CLITask,
    CLITaskPriority,
    CLITaskStatus,
    CLITaskType,
)

logger = get_logger(__name__)

# Constants for output size limits
MAX_STDOUT_SIZE = 100_000  # 100KB
MAX_STDERR_SIZE = 10_000  # 10KB
MAX_ERROR_MESSAGE_LENGTH = 1_000
MAX_ERROR_LOG_LENGTH = 500
MAX_ERROR_DISPLAY_LENGTH = 200

# Default task configuration
DEFAULT_TIMEOUT_SECONDS = 3600  # 1 hour
DEFAULT_MAX_RETRIES = 3
MAX_BATCH_SIZE = 1000

# Directory for CLI task outputs (lazily initialized)
_cli_output_dir: Path | None = None


def get_cli_output_dir() -> Path:
    """
    Get the CLI output directory, creating it if necessary.

    Returns:
        Path to the CLI output directory
    """
    global _cli_output_dir
    if _cli_output_dir is None:
        _cli_output_dir = Path(settings.cli_task_output_dir)
    _cli_output_dir.mkdir(parents=True, exist_ok=True)
    return _cli_output_dir


# Patterns that may indicate dangerous commands (for logging/audit only)
# Production deployments should implement proper sandboxing
POTENTIALLY_DANGEROUS_PATTERNS = [
    r'\brm\s+-rf\s+/',  # rm -rf with root path
    r'\bsudo\b',  # sudo commands
    r'\bchmod\s+777\b',  # overly permissive chmod
    r'>\s*/etc/',  # writing to /etc
    r'\bcurl\b.*\|\s*\bsh\b',  # curl piped to shell
    r'\bwget\b.*\|\s*\bsh\b',  # wget piped to shell
]


def _check_command_safety(command: str) -> list[str]:
    """
    Check command for potentially dangerous patterns.

    This is for logging/audit purposes only. Production deployments
    should implement proper sandboxing or command allowlisting.

    Args:
        command: The command to check

    Returns:
        List of matched warning patterns (empty if none found)
    """
    warnings = []
    for pattern in POTENTIALLY_DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            warnings.append(pattern)
    return warnings


class CLITaskService:
    """
    Service for managing CLI task operations.

    Provides methods for submitting, executing, monitoring,
    and managing long-running CLI tasks.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the CLI task service.

        Args:
            db: Database session for operations
        """
        self.db = db
        self._running_processes: dict[UUID, asyncio.subprocess.Process] = {}

    async def submit_task(
        self,
        name: str,
        task_type: CLITaskType,
        command: str,
        description: str | None = None,
        input_data: dict[str, Any] | None = None,
        input_file_path: str | None = None,
        working_directory: str | None = None,
        environment_vars: dict[str, str] | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        priority: CLITaskPriority = CLITaskPriority.NORMAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        engagement_id: UUID | None = None,
        user_id: UUID | None = None,
        trace_id: str | None = None,
        parent_task_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CLITask:
        """
        Submit a new CLI task for execution.

        Args:
            name: Human-readable task name
            task_type: Type of CLI task
            command: CLI command to execute
            description: Optional task description
            input_data: Optional input parameters
            input_file_path: Optional path to input file
            working_directory: Optional working directory
            environment_vars: Optional environment variables
            timeout_seconds: Maximum execution time
            priority: Task priority level
            max_retries: Maximum retry attempts
            engagement_id: Associated engagement ID
            user_id: User submitting the task
            trace_id: OpenAI Agents SDK trace ID
            parent_task_id: Parent task ID for batch operations
            metadata: Additional metadata

        Returns:
            Created CLITask record
        """
        # Check command for potentially dangerous patterns (logging only)
        safety_warnings = _check_command_safety(command)
        if safety_warnings:
            logger.warning(
                "CLI task command contains potentially dangerous patterns",
                name=name,
                command=command[:100],
                warnings=safety_warnings,
            )

        task = CLITask(
            name=name,
            task_type=task_type,
            command=command,
            description=description,
            status=CLITaskStatus.PENDING,
            priority=priority,
            input_data=input_data or {},
            input_file_path=input_file_path,
            working_directory=working_directory,
            environment_vars=environment_vars or {},
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            engagement_id=engagement_id,
            parent_task_id=parent_task_id,
            trace_id=trace_id,
            created_by=user_id,
            updated_by=user_id,
            extra_metadata=metadata or {
                "environment": settings.environment,
                "app_version": settings.app_version,
            },
        )
        self.db.add(task)
        await self.db.flush()

        logger.info(
            "CLI task submitted",
            task_id=str(task.id),
            task_type=task_type.value,
            name=name,
            command=command[:100],
        )

        # Create audit log entry
        audit_log = AuditLog.create(
            action=AuditAction.WORKFLOW_START,
            resource_type="cli_task",
            resource_id=task.id,
            description=f"CLI task submitted: {name}",
            user_id=user_id,
            trace_id=trace_id,
            severity=AuditSeverity.INFO,
            metadata={
                "task_type": task_type.value,
                "command": command[:500],
                "priority": priority.value,
            },
        )
        self.db.add(audit_log)

        return task

    async def execute_task(
        self,
        task: CLITask,
        capture_output: bool = True,
    ) -> CLITask:
        """
        Execute a CLI task.

        Args:
            task: Task to execute
            capture_output: Whether to capture stdout/stderr

        Returns:
            Updated CLITask with results
        """
        if task.status not in (CLITaskStatus.PENDING, CLITaskStatus.QUEUED):
            raise ValueError(f"Cannot execute task in status: {task.status.value}")

        # Mark as in progress
        task.queue()
        await self.db.flush()

        task.start()
        await self.db.flush()

        try:
            # Prepare execution environment
            env = os.environ.copy()
            if task.environment_vars:
                env.update(task.environment_vars)

            cwd = task.working_directory or str(Path.cwd())

            logger.info(
                "Executing CLI task",
                task_id=str(task.id),
                command=task.command[:100],
            )

            # Execute the command
            process = await asyncio.create_subprocess_shell(
                task.command,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=cwd,
                env=env,
            )

            # Store process reference
            self._running_processes[task.id] = process
            task.process_id = process.pid
            await self.db.flush()

            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=task.timeout_seconds,
                )

                exit_code = process.returncode or 0

                # Process output
                output_data: dict[str, Any] = {}
                if capture_output:
                    if stdout:
                        stdout_text = stdout.decode("utf-8", errors="replace")
                        output_data["stdout"] = stdout_text[:MAX_STDOUT_SIZE]

                        # Try to parse JSON output
                        try:
                            output_data["parsed"] = json.loads(stdout_text)
                        except json.JSONDecodeError:
                            pass

                    if stderr:
                        output_data["stderr"] = stderr.decode("utf-8", errors="replace")[:MAX_STDERR_SIZE]

                if exit_code == 0:
                    # Success
                    task.complete(
                        output_data=output_data,
                        exit_code=exit_code,
                    )

                    logger.info(
                        "CLI task completed successfully",
                        task_id=str(task.id),
                        exit_code=exit_code,
                        duration=task.duration_seconds,
                    )

                    # Create success audit log
                    audit_log = AuditLog.create(
                        action=AuditAction.WORKFLOW_COMPLETE,
                        resource_type="cli_task",
                        resource_id=task.id,
                        description=f"CLI task completed: {task.name}",
                        user_id=task.created_by,
                        trace_id=task.trace_id,
                        severity=AuditSeverity.INFO,
                        metadata={
                            "exit_code": exit_code,
                            "duration_seconds": task.duration_seconds,
                        },
                    )
                    self.db.add(audit_log)
                else:
                    # Command failed
                    error_msg = output_data.get("stderr", f"Command exited with code {exit_code}")
                    task.fail(
                        error_message=error_msg[:MAX_ERROR_MESSAGE_LENGTH],
                        error_details=output_data,
                        exit_code=exit_code,
                    )

                    logger.error(
                        "CLI task failed",
                        task_id=str(task.id),
                        exit_code=exit_code,
                        error=error_msg[:MAX_ERROR_DISPLAY_LENGTH],
                    )

                    # Create failure audit log
                    audit_log = AuditLog.create(
                        action=AuditAction.WORKFLOW_COMPLETE,
                        resource_type="cli_task",
                        resource_id=task.id,
                        description=f"CLI task failed: {task.name}",
                        user_id=task.created_by,
                        trace_id=task.trace_id,
                        severity=AuditSeverity.ERROR,
                        metadata={
                            "exit_code": exit_code,
                            "error": error_msg[:MAX_ERROR_LOG_LENGTH],
                        },
                    )
                    self.db.add(audit_log)

            except asyncio.TimeoutError:
                # Kill the process
                process.kill()
                await process.wait()

                task.timeout()

                logger.error(
                    "CLI task timed out",
                    task_id=str(task.id),
                    timeout_seconds=task.timeout_seconds,
                )

                # Create timeout audit log
                audit_log = AuditLog.create(
                    action=AuditAction.WORKFLOW_COMPLETE,
                    resource_type="cli_task",
                    resource_id=task.id,
                    description=f"CLI task timed out: {task.name}",
                    user_id=task.created_by,
                    trace_id=task.trace_id,
                    severity=AuditSeverity.ERROR,
                    metadata={
                        "timeout_seconds": task.timeout_seconds,
                    },
                )
                self.db.add(audit_log)

        except Exception as e:
            task.fail(
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

            logger.error(
                "CLI task execution error",
                task_id=str(task.id),
                error=str(e),
                exc_info=True,
            )

            # Create error audit log
            audit_log = AuditLog.create(
                action=AuditAction.WORKFLOW_COMPLETE,
                resource_type="cli_task",
                resource_id=task.id,
                description=f"CLI task error: {task.name}",
                user_id=task.created_by,
                trace_id=task.trace_id,
                severity=AuditSeverity.CRITICAL,
                metadata={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            self.db.add(audit_log)

        finally:
            # Clean up process reference
            self._running_processes.pop(task.id, None)

        await self.db.flush()
        return task

    async def execute_task_background(
        self,
        task: CLITask,
    ) -> CLITask:
        """
        Start task execution in background.

        Returns immediately after starting the task.
        Use get_task_status to poll for completion.

        Args:
            task: Task to execute

        Returns:
            Task with status updated to QUEUED
        """
        task.queue()
        await self.db.flush()

        # Schedule execution in background with error handling
        asyncio.create_task(self._safe_execute_and_update(task.id))

        return task

    async def _safe_execute_and_update(self, task_id: UUID) -> None:
        """
        Execute task with exception handling for background execution.

        Wraps _execute_and_update to catch and log any exceptions
        that would otherwise be lost in background task execution.
        """
        try:
            await self._execute_and_update(task_id)
        except Exception as e:
            logger.error(
                "Background task execution failed",
                task_id=str(task_id),
                error=str(e),
                exc_info=True,
            )
            # Attempt to mark task as failed
            try:
                from core.database import get_db_context

                async with get_db_context() as db:
                    service = CLITaskService(db)
                    task = await service.get_task(task_id)
                    if task and task.is_running:
                        task.fail(
                            error_message=f"Background execution error: {str(e)[:MAX_ERROR_MESSAGE_LENGTH - 30]}",
                            error_details={"exception_type": type(e).__name__},
                        )
                        await db.commit()
            except Exception as inner_e:
                logger.error(
                    "Failed to mark background task as failed",
                    task_id=str(task_id),
                    error=str(inner_e),
                )

    async def _execute_and_update(self, task_id: UUID) -> None:
        """Execute task and update status (background task helper)."""
        from core.database import get_db_context

        async with get_db_context() as db:
            service = CLITaskService(db)
            task = await service.get_task(task_id)
            if task:
                await service.execute_task(task)
                await db.commit()

    async def get_task(self, task_id: UUID) -> CLITask | None:
        """
        Get a task by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            CLITask or None if not found
        """
        stmt = select(CLITask).where(CLITask.id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_task_status(self, task_id: UUID) -> dict[str, Any] | None:
        """
        Get task status summary.

        Args:
            task_id: Task ID

        Returns:
            Status dictionary or None if not found
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        return {
            "id": str(task.id),
            "name": task.name,
            "task_type": task.task_type.value,
            "status": task.status.value,
            "progress_percentage": task.progress_percentage,
            "progress_message": task.progress_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "duration_seconds": task.duration_seconds,
            "error_message": task.error_message,
            "is_running": task.is_running,
            "is_finished": task.is_finished,
        }

    async def list_tasks(
        self,
        status: CLITaskStatus | None = None,
        task_type: CLITaskType | None = None,
        engagement_id: UUID | None = None,
        parent_task_id: UUID | None = None,
        limit: int = 50,
    ) -> list[CLITask]:
        """
        List tasks with optional filtering.

        Args:
            status: Optional status filter
            task_type: Optional type filter
            engagement_id: Optional engagement filter
            parent_task_id: Optional parent task filter
            limit: Maximum results

        Returns:
            List of CLITask records
        """
        stmt = select(CLITask).order_by(CLITask.created_at.desc()).limit(limit)

        if status:
            stmt = stmt.where(CLITask.status == status)
        if task_type:
            stmt = stmt.where(CLITask.task_type == task_type)
        if engagement_id:
            stmt = stmt.where(CLITask.engagement_id == engagement_id)
        if parent_task_id:
            stmt = stmt.where(CLITask.parent_task_id == parent_task_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def cancel_task(
        self,
        task_id: UUID,
        reason: str | None = None,
        user_id: UUID | None = None,
    ) -> CLITask | None:
        """
        Cancel a running task.

        Args:
            task_id: Task to cancel
            reason: Cancellation reason
            user_id: User cancelling the task

        Returns:
            Updated task or None if not found
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        if not task.is_running:
            raise ValueError(f"Cannot cancel task in status: {task.status.value}")

        # Try to kill the process if running
        process = self._running_processes.get(task_id)
        if process:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass  # Process already terminated

        task.cancel(reason)
        task.updated_by = user_id

        # Create cancellation audit log
        audit_log = AuditLog.create(
            action=AuditAction.WORKFLOW_COMPLETE,
            resource_type="cli_task",
            resource_id=task.id,
            description=f"CLI task cancelled: {task.name}",
            user_id=user_id,
            trace_id=task.trace_id,
            severity=AuditSeverity.WARNING,
            metadata={"reason": reason},
        )
        self.db.add(audit_log)

        await self.db.flush()

        logger.info(
            "CLI task cancelled",
            task_id=str(task_id),
            reason=reason,
        )

        return task

    async def retry_task(
        self,
        task_id: UUID,
        user_id: UUID | None = None,
    ) -> CLITask | None:
        """
        Retry a failed task.

        Args:
            task_id: Task to retry
            user_id: User initiating retry

        Returns:
            Updated task or None if not found
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        if not task.can_retry():
            raise ValueError(
                f"Task cannot be retried. Status: {task.status.value}, "
                f"Retry count: {task.retry_count}/{task.max_retries}"
            )

        task.prepare_retry()
        task.updated_by = user_id

        # Create retry audit log
        audit_log = AuditLog.create(
            action=AuditAction.WORKFLOW_START,
            resource_type="cli_task",
            resource_id=task.id,
            description=f"CLI task retry initiated: {task.name}",
            user_id=user_id,
            trace_id=task.trace_id,
            severity=AuditSeverity.INFO,
            metadata={"retry_count": task.retry_count},
        )
        self.db.add(audit_log)

        await self.db.flush()

        logger.info(
            "CLI task retry initiated",
            task_id=str(task_id),
            retry_count=task.retry_count,
        )

        return task

    async def submit_batch(
        self,
        name: str,
        task_type: CLITaskType,
        commands: list[str],
        description: str | None = None,
        user_id: UUID | None = None,
        engagement_id: UUID | None = None,
        trace_id: str | None = None,
    ) -> CLITask:
        """
        Submit a batch of tasks under a parent task.

        Args:
            name: Batch name
            task_type: Type for all tasks
            commands: List of commands to execute
            description: Batch description
            user_id: User submitting the batch
            engagement_id: Associated engagement
            trace_id: Trace ID for correlation

        Returns:
            Parent CLITask representing the batch
        """
        # Create parent task
        parent_task = await self.submit_task(
            name=f"Batch: {name}",
            task_type=task_type,
            command=f"Batch of {len(commands)} tasks",
            description=description or f"Batch processing {len(commands)} tasks",
            user_id=user_id,
            engagement_id=engagement_id,
            trace_id=trace_id,
            metadata={
                "batch_size": len(commands),
                "is_batch_parent": True,
            },
        )

        # Create child tasks
        for i, command in enumerate(commands):
            await self.submit_task(
                name=f"{name} ({i + 1}/{len(commands)})",
                task_type=task_type,
                command=command,
                description=f"Batch task {i + 1} of {len(commands)}",
                user_id=user_id,
                engagement_id=engagement_id,
                trace_id=trace_id,
                parent_task_id=parent_task.id,
                metadata={"batch_index": i},
            )

        logger.info(
            "Batch submitted",
            parent_task_id=str(parent_task.id),
            batch_size=len(commands),
        )

        return parent_task

    async def get_batch_status(self, parent_task_id: UUID) -> dict[str, Any] | None:
        """
        Get status of a batch operation.

        Args:
            parent_task_id: Parent task ID

        Returns:
            Batch status summary or None if not found
        """
        parent = await self.get_task(parent_task_id)
        if not parent:
            return None

        children = await self.list_tasks(parent_task_id=parent_task_id, limit=1000)

        total = len(children)
        completed = sum(1 for t in children if t.status == CLITaskStatus.COMPLETED)
        failed = sum(1 for t in children if t.status == CLITaskStatus.FAILED)
        running = sum(1 for t in children if t.is_running)
        pending = sum(1 for t in children if t.status == CLITaskStatus.PENDING)

        return {
            "parent_task_id": str(parent_task_id),
            "name": parent.name,
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "is_complete": (completed + failed) == total,
            "has_failures": failed > 0,
        }


async def get_cli_task_service(db: AsyncSession) -> CLITaskService:
    """
    FastAPI dependency for getting a CLITaskService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured CLITaskService instance
    """
    return CLITaskService(db)
