"""
Codex CLI function tools for agents using OpenAI Agents SDK.

Provides tools for long-running task execution, batch processing,
and external system calls through the Codex CLI integration.
Uses the @function_tool decorator from the agents SDK.
"""

import json
from uuid import UUID

from agents import function_tool

from core.database import get_db_context
from core.logging import get_logger
from models.cli_task import CLITaskPriority, CLITaskStatus, CLITaskType
from services.cli_task_service import CLITaskService

logger = get_logger(__name__)

# Constants for tool output limits
MAX_TOOL_OUTPUT_SIZE = 5_000  # Maximum characters for tool output
MAX_BATCH_SIZE = 100  # Maximum commands in a batch
MAX_LIST_LIMIT = 100  # Maximum tasks to return in list

# Shared type mappings to avoid DRY violations
TASK_TYPE_MAP: dict[str, CLITaskType] = {
    "shell_command": CLITaskType.SHELL_COMMAND,
    "data_validation": CLITaskType.DATA_VALIDATION,
    "data_transformation": CLITaskType.DATA_TRANSFORMATION,
    "reserve_calculation": CLITaskType.RESERVE_CALCULATION,
    "ibnr_estimation": CLITaskType.IBNR_ESTIMATION,
    "ifrs17_calculation": CLITaskType.IFRS17_CALCULATION,
    "alm_model": CLITaskType.ALM_MODEL,
    "batch_import": CLITaskType.BATCH_IMPORT,
    "report_generation": CLITaskType.REPORT_GENERATION,
    "export_data": CLITaskType.EXPORT_DATA,
    "custom_script": CLITaskType.CUSTOM_SCRIPT,
}

PRIORITY_MAP: dict[str, CLITaskPriority] = {
    "low": CLITaskPriority.LOW,
    "normal": CLITaskPriority.NORMAL,
    "high": CLITaskPriority.HIGH,
    "critical": CLITaskPriority.CRITICAL,
}

STATUS_MAP: dict[str, CLITaskStatus] = {
    "pending": CLITaskStatus.PENDING,
    "queued": CLITaskStatus.QUEUED,
    "in_progress": CLITaskStatus.IN_PROGRESS,
    "completed": CLITaskStatus.COMPLETED,
    "failed": CLITaskStatus.FAILED,
    "cancelled": CLITaskStatus.CANCELLED,
    "timeout": CLITaskStatus.TIMEOUT,
}


def _get_task_type(task_type: str) -> CLITaskType:
    """Get CLITaskType from string, defaulting to SHELL_COMMAND."""
    return TASK_TYPE_MAP.get(task_type.lower(), CLITaskType.SHELL_COMMAND)


def _get_priority(priority: str) -> CLITaskPriority:
    """Get CLITaskPriority from string, defaulting to NORMAL."""
    return PRIORITY_MAP.get(priority.lower(), CLITaskPriority.NORMAL)


def _get_status(status: str) -> CLITaskStatus | None:
    """Get CLITaskStatus from string, returning None if not found."""
    return STATUS_MAP.get(status.lower())


@function_tool
async def submit_cli_task(
    name: str,
    command: str,
    task_type: str = "shell_command",
    description: str | None = None,
    timeout_seconds: int = 3600,
    priority: str = "normal",
) -> str:
    """
    Submit a CLI task for execution.

    Use this tool to execute long-running shell commands, scripts,
    or external system calls. The task will be executed asynchronously
    and you can check its status using the get_cli_task_status tool.

    Args:
        name: A human-readable name for the task
        command: The shell command to execute
        task_type: Type of task - one of: shell_command, data_validation,
                   data_transformation, reserve_calculation, report_generation
        description: Optional description of what the task does
        timeout_seconds: Maximum execution time (default: 3600 = 1 hour)
        priority: Execution priority - one of: low, normal, high, critical

    Returns:
        JSON string with task_id and initial status
    """
    cli_task_type = _get_task_type(task_type)
    cli_priority = _get_priority(priority)

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            task = await service.submit_task(
                name=name,
                task_type=cli_task_type,
                command=command,
                description=description,
                timeout_seconds=timeout_seconds,
                priority=cli_priority,
            )

            return json.dumps({
                "success": True,
                "task_id": str(task.id),
                "name": task.name,
                "status": task.status.value,
                "message": f"Task '{name}' submitted successfully. Use get_cli_task_status with task_id '{task.id}' to check progress.",
            })

    except Exception as e:
        logger.error("Failed to submit CLI task", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "message": f"Failed to submit task: {str(e)}",
        })


@function_tool
async def execute_cli_task(
    name: str,
    command: str,
    task_type: str = "shell_command",
    description: str | None = None,
    timeout_seconds: int = 300,
) -> str:
    """
    Execute a CLI task and wait for completion.

    Use this tool for shorter tasks (under 5 minutes) where you want
    to wait for the result. For longer tasks, use submit_cli_task
    and poll with get_cli_task_status.

    Args:
        name: A human-readable name for the task
        command: The shell command to execute
        task_type: Type of task (default: shell_command)
        description: Optional description
        timeout_seconds: Maximum wait time (default: 300 = 5 minutes)

    Returns:
        JSON string with task results and output
    """
    cli_task_type = _get_task_type(task_type)

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)

            # Submit and execute
            task = await service.submit_task(
                name=name,
                task_type=cli_task_type,
                command=command,
                description=description,
                timeout_seconds=timeout_seconds,
            )

            task = await service.execute_task(task)

            result = {
                "success": task.status == CLITaskStatus.COMPLETED,
                "task_id": str(task.id),
                "name": task.name,
                "status": task.status.value,
                "exit_code": task.exit_code,
                "duration_seconds": task.duration_seconds,
            }

            if task.output_data:
                # Return stdout if available
                if "stdout" in task.output_data:
                    result["output"] = task.output_data["stdout"][:MAX_TOOL_OUTPUT_SIZE]
                if "parsed" in task.output_data:
                    result["parsed_output"] = task.output_data["parsed"]

            if task.error_message:
                result["error"] = task.error_message

            return json.dumps(result)

    except Exception as e:
        logger.error("Failed to execute CLI task", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "message": f"Failed to execute task: {str(e)}",
        })


@function_tool
async def get_cli_task_status(task_id: str) -> str:
    """
    Get the current status of a CLI task.

    Use this to check the progress and status of a previously
    submitted task.

    Args:
        task_id: The UUID of the task to check

    Returns:
        JSON string with current task status and progress
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Invalid task_id format. Must be a valid UUID.",
        })

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            status = await service.get_task_status(task_uuid)

            if not status:
                return json.dumps({
                    "success": False,
                    "error": f"Task not found: {task_id}",
                })

            return json.dumps({
                "success": True,
                **status,
            })

    except Exception as e:
        logger.error("Failed to get task status", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@function_tool
async def get_cli_task_result(task_id: str) -> str:
    """
    Get the full result of a completed CLI task.

    Use this after a task has completed to retrieve its output data.

    Args:
        task_id: The UUID of the task

    Returns:
        JSON string with task results including output data
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Invalid task_id format. Must be a valid UUID.",
        })

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            task = await service.get_task(task_uuid)

            if not task:
                return json.dumps({
                    "success": False,
                    "error": f"Task not found: {task_id}",
                })

            result = {
                "success": task.status == CLITaskStatus.COMPLETED,
                "task_id": str(task.id),
                "name": task.name,
                "status": task.status.value,
                "task_type": task.task_type.value,
                "exit_code": task.exit_code,
                "duration_seconds": task.duration_seconds,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

            if task.output_data:
                result["output_data"] = task.output_data

            if task.output_file_path:
                result["output_file_path"] = task.output_file_path

            if task.error_message:
                result["error"] = task.error_message

            if task.error_details:
                result["error_details"] = task.error_details

            return json.dumps(result, default=str)

    except Exception as e:
        logger.error("Failed to get task result", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@function_tool
async def cancel_cli_task(task_id: str, reason: str | None = None) -> str:
    """
    Cancel a running CLI task.

    Use this to stop a task that is currently executing.

    Args:
        task_id: The UUID of the task to cancel
        reason: Optional reason for cancellation

    Returns:
        JSON string with cancellation result
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Invalid task_id format. Must be a valid UUID.",
        })

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            task = await service.cancel_task(task_uuid, reason=reason)

            if not task:
                return json.dumps({
                    "success": False,
                    "error": f"Task not found: {task_id}",
                })

            return json.dumps({
                "success": True,
                "task_id": str(task.id),
                "status": task.status.value,
                "message": f"Task '{task.name}' has been cancelled.",
            })

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e),
        })
    except Exception as e:
        logger.error("Failed to cancel task", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@function_tool
async def list_cli_tasks(
    status: str | None = None,
    task_type: str | None = None,
    limit: int = 20,
) -> str:
    """
    List recent CLI tasks with optional filtering.

    Use this to see recent tasks and their statuses.

    Args:
        status: Optional filter by status (pending, in_progress, completed, failed)
        task_type: Optional filter by task type
        limit: Maximum number of tasks to return (default: 20)

    Returns:
        JSON string with list of tasks
    """
    try:
        async with get_db_context() as db:
            service = CLITaskService(db)

            # Map status and task type strings to enums
            status_enum = _get_status(status) if status else None
            type_enum = _get_task_type(task_type) if task_type else None

            tasks = await service.list_tasks(
                status=status_enum,
                task_type=type_enum,
                limit=min(limit, MAX_LIST_LIMIT),
            )

            return json.dumps({
                "success": True,
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "name": t.name,
                        "task_type": t.task_type.value,
                        "status": t.status.value,
                        "progress": t.progress_percentage,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "duration_seconds": t.duration_seconds,
                    }
                    for t in tasks
                ],
            })

    except Exception as e:
        logger.error("Failed to list tasks", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@function_tool
async def submit_batch_tasks(
    name: str,
    commands: list[str],
    task_type: str = "shell_command",
    description: str | None = None,
) -> str:
    """
    Submit multiple commands as a batch operation.

    Use this to run multiple related commands as a single batch.
    Returns a parent task ID that can be used to track overall progress.

    Args:
        name: Name for the batch operation
        commands: List of shell commands to execute
        task_type: Type for all tasks in the batch
        description: Optional description of the batch

    Returns:
        JSON string with parent task ID and batch details
    """
    if not commands:
        return json.dumps({
            "success": False,
            "error": "No commands provided for batch",
        })

    if len(commands) > MAX_BATCH_SIZE:
        return json.dumps({
            "success": False,
            "error": f"Maximum batch size is {MAX_BATCH_SIZE} commands",
        })

    cli_task_type = _get_task_type(task_type)

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            parent_task = await service.submit_batch(
                name=name,
                task_type=cli_task_type,
                commands=commands,
                description=description,
            )

            return json.dumps({
                "success": True,
                "parent_task_id": str(parent_task.id),
                "batch_name": parent_task.name,
                "batch_size": len(commands),
                "message": f"Batch '{name}' submitted with {len(commands)} tasks. Use get_batch_status with parent_task_id to monitor progress.",
            })

    except Exception as e:
        logger.error("Failed to submit batch", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@function_tool
async def get_batch_status(parent_task_id: str) -> str:
    """
    Get the status of a batch operation.

    Use this to check progress of a batch submitted with submit_batch_tasks.

    Args:
        parent_task_id: The UUID of the parent batch task

    Returns:
        JSON string with batch progress summary
    """
    try:
        task_uuid = UUID(parent_task_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": "Invalid parent_task_id format. Must be a valid UUID.",
        })

    try:
        async with get_db_context() as db:
            service = CLITaskService(db)
            status = await service.get_batch_status(task_uuid)

            if not status:
                return json.dumps({
                    "success": False,
                    "error": f"Batch task not found: {parent_task_id}",
                })

            return json.dumps({
                "success": True,
                **status,
            })

    except Exception as e:
        logger.error("Failed to get batch status", error=str(e), exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
        })


# Export all Codex CLI tools for easy import
CODEX_TOOLS = [
    submit_cli_task,
    execute_cli_task,
    get_cli_task_status,
    get_cli_task_result,
    cancel_cli_task,
    list_cli_tasks,
    submit_batch_tasks,
    get_batch_status,
]
