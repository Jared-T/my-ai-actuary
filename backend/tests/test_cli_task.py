"""
Tests for CLI Task models and Codex CLI integration.

Verifies that all CLI task models and services are properly defined.
Tests model instantiation, lifecycle methods, and configuration.

This is a verification test file to ensure the Codex CLI integration
feature is working correctly.
"""

import pytest
from uuid import uuid4


# Test CLI Task model imports
def test_cli_task_model_imports():
    """Verify CLI Task models can be imported."""
    from models import (
        CLITask,
        CLITaskStatus,
        CLITaskType,
        CLITaskPriority,
    )

    assert CLITask is not None
    assert CLITaskStatus is not None
    assert CLITaskType is not None
    assert CLITaskPriority is not None


def test_cli_task_status_enum():
    """Test CLITaskStatus enum values."""
    from models import CLITaskStatus

    assert CLITaskStatus.PENDING.value == "pending"
    assert CLITaskStatus.QUEUED.value == "queued"
    assert CLITaskStatus.IN_PROGRESS.value == "in_progress"
    assert CLITaskStatus.COMPLETED.value == "completed"
    assert CLITaskStatus.FAILED.value == "failed"
    assert CLITaskStatus.CANCELLED.value == "cancelled"
    assert CLITaskStatus.TIMEOUT.value == "timeout"


def test_cli_task_type_enum():
    """Test CLITaskType enum values."""
    from models import CLITaskType

    # Actuarial calculation types
    assert CLITaskType.RESERVE_CALCULATION.value == "reserve_calculation"
    assert CLITaskType.IBNR_ESTIMATION.value == "ibnr_estimation"
    assert CLITaskType.IFRS17_CALCULATION.value == "ifrs17_calculation"
    assert CLITaskType.ALM_MODEL.value == "alm_model"

    # Data processing types
    assert CLITaskType.DATA_VALIDATION.value == "data_validation"
    assert CLITaskType.DATA_TRANSFORMATION.value == "data_transformation"
    assert CLITaskType.BATCH_IMPORT.value == "batch_import"

    # Reporting types
    assert CLITaskType.REPORT_GENERATION.value == "report_generation"
    assert CLITaskType.EXPORT_DATA.value == "export_data"

    # Generic types
    assert CLITaskType.SHELL_COMMAND.value == "shell_command"
    assert CLITaskType.CUSTOM_SCRIPT.value == "custom_script"


def test_cli_task_priority_enum():
    """Test CLITaskPriority enum values."""
    from models import CLITaskPriority

    assert CLITaskPriority.LOW.value == "low"
    assert CLITaskPriority.NORMAL.value == "normal"
    assert CLITaskPriority.HIGH.value == "high"
    assert CLITaskPriority.CRITICAL.value == "critical"


def test_cli_task_model_instantiation():
    """Test CLITask model can be instantiated."""
    from models import CLITask, CLITaskStatus, CLITaskType, CLITaskPriority

    task = CLITask(
        name="Test CLI Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="echo 'Hello World'",
        description="Test command execution",
        status=CLITaskStatus.PENDING,
        priority=CLITaskPriority.NORMAL,
        timeout_seconds=300,
    )

    assert task.name == "Test CLI Task"
    assert task.task_type == CLITaskType.SHELL_COMMAND
    assert task.command == "echo 'Hello World'"
    assert task.status == CLITaskStatus.PENDING
    assert task.priority == CLITaskPriority.NORMAL
    assert task.timeout_seconds == 300


def test_cli_task_queue_method():
    """Test CLITask queue method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls -la",
        status=CLITaskStatus.PENDING,
    )

    assert task.queued_at is None
    task.queue()

    assert task.status == CLITaskStatus.QUEUED
    assert task.queued_at is not None


def test_cli_task_start_method():
    """Test CLITask start method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls -la",
        status=CLITaskStatus.PENDING,
    )

    task.start(process_id=12345)

    assert task.status == CLITaskStatus.IN_PROGRESS
    assert task.started_at is not None
    assert task.process_id == 12345
    assert task.progress_percentage == 0.0


def test_cli_task_complete_method():
    """Test CLITask complete method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls -la",
        status=CLITaskStatus.PENDING,
    )

    task.start()
    output_data = {"stdout": "file1.txt\nfile2.txt"}
    task.complete(output_data=output_data, exit_code=0)

    assert task.status == CLITaskStatus.COMPLETED
    assert task.completed_at is not None
    assert task.progress_percentage == 100.0
    assert task.exit_code == 0
    assert task.output_data == output_data


def test_cli_task_fail_method():
    """Test CLITask fail method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="invalid_command",
        status=CLITaskStatus.PENDING,
    )

    task.start()
    task.fail(
        error_message="Command not found",
        error_details={"stderr": "bash: invalid_command: command not found"},
        exit_code=127,
    )

    assert task.status == CLITaskStatus.FAILED
    assert task.completed_at is not None
    assert task.error_message == "Command not found"
    assert task.exit_code == 127
    assert task.error_details["stderr"] == "bash: invalid_command: command not found"


def test_cli_task_timeout_method():
    """Test CLITask timeout method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="sleep 1000",
        status=CLITaskStatus.PENDING,
        timeout_seconds=60,
    )

    task.start()
    task.timeout()

    assert task.status == CLITaskStatus.TIMEOUT
    assert task.completed_at is not None
    assert "60 seconds" in task.error_message


def test_cli_task_cancel_method():
    """Test CLITask cancel method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="long_running_process",
        status=CLITaskStatus.PENDING,
    )

    task.start()
    task.cancel(reason="User requested cancellation")

    assert task.status == CLITaskStatus.CANCELLED
    assert task.completed_at is not None
    assert "User requested cancellation" in task.error_message


def test_cli_task_retry_logic():
    """Test CLITask retry logic."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="flaky_command",
        status=CLITaskStatus.PENDING,
        max_retries=3,
        retry_count=0,  # Explicitly set for tests (DB default is 0)
    )

    # Simulate initial failure
    task.start()
    task.fail("Network error")

    # Check retry capability
    assert task.can_retry() is True
    assert task.retry_count == 0

    # Prepare for retry
    task.prepare_retry()
    assert task.status == CLITaskStatus.PENDING
    assert task.retry_count == 1
    assert task.error_message is None

    # Retry and fail again
    task.start()
    task.fail("Network error again")
    task.prepare_retry()
    assert task.retry_count == 2

    # Third attempt
    task.start()
    task.fail("Network error once more")
    task.prepare_retry()
    assert task.retry_count == 3

    # Fourth failure - should not be able to retry
    task.start()
    task.fail("Final failure")
    assert task.can_retry() is False


def test_cli_task_update_progress():
    """Test CLITask progress update method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.DATA_TRANSFORMATION,
        command="process_data.py",
        status=CLITaskStatus.PENDING,
    )

    task.start()

    # Update progress
    task.update_progress(25.0, "Processing batch 1 of 4")
    assert task.progress_percentage == 25.0
    assert task.progress_message == "Processing batch 1 of 4"

    # Test bounds clamping
    task.update_progress(150.0)  # Should clamp to 100
    assert task.progress_percentage == 100.0

    task.update_progress(-10.0)  # Should clamp to 0
    assert task.progress_percentage == 0.0


def test_cli_task_duration_property():
    """Test CLITask duration_seconds property."""
    from models import CLITask, CLITaskStatus, CLITaskType
    from datetime import datetime, timezone, timedelta

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="sleep 5",
        status=CLITaskStatus.PENDING,
    )

    # Before start, duration is None
    assert task.duration_seconds is None

    # Simulate started time
    task.start()
    # Duration should be a small positive number
    assert task.duration_seconds is not None
    assert task.duration_seconds >= 0


def test_cli_task_is_running_property():
    """Test CLITask is_running property."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls",
        status=CLITaskStatus.PENDING,
    )

    assert task.is_running is False

    task.queue()
    assert task.is_running is True

    task.start()
    assert task.is_running is True

    task.complete()
    assert task.is_running is False


def test_cli_task_is_finished_property():
    """Test CLITask is_finished property."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls",
        status=CLITaskStatus.PENDING,
    )

    assert task.is_finished is False

    task.start()
    assert task.is_finished is False

    task.complete()
    assert task.is_finished is True


def test_cli_task_with_engagement_id():
    """Test CLITask with engagement association."""
    from models import CLITask, CLITaskType

    engagement_id = uuid4()

    task = CLITask(
        name="Engagement Task",
        task_type=CLITaskType.RESERVE_CALCULATION,
        command="calculate_reserves.py --engagement={engagement_id}",
        engagement_id=engagement_id,
    )

    assert task.engagement_id == engagement_id


def test_cli_task_with_parent_task():
    """Test CLITask with parent task (batch operations)."""
    from models import CLITask, CLITaskType

    parent_id = uuid4()

    task = CLITask(
        name="Batch Child Task",
        task_type=CLITaskType.DATA_VALIDATION,
        command="validate_batch_1.py",
        parent_task_id=parent_id,
    )

    assert task.parent_task_id == parent_id


def test_cli_task_with_trace_id():
    """Test CLITask with OpenAI Agents SDK trace ID."""
    from models import CLITask, CLITaskType

    trace_id = "trace_abc123xyz789"

    task = CLITask(
        name="Traced Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="traced_command",
        trace_id=trace_id,
    )

    assert task.trace_id == trace_id


def test_cli_task_service_import():
    """Test CLI task service can be imported."""
    from services import CLITaskService, get_cli_task_service

    assert CLITaskService is not None
    assert get_cli_task_service is not None


def test_codex_tools_import():
    """Test Codex CLI tools can be imported."""
    from tools import (
        CODEX_TOOLS,
        submit_cli_task,
        execute_cli_task,
        get_cli_task_status,
        get_cli_task_result,
        cancel_cli_task,
        list_cli_tasks,
        submit_batch_tasks,
        get_batch_status,
    )

    assert CODEX_TOOLS is not None
    assert len(CODEX_TOOLS) == 8

    # Verify all tools are in the list
    assert submit_cli_task in CODEX_TOOLS
    assert execute_cli_task in CODEX_TOOLS
    assert get_cli_task_status in CODEX_TOOLS
    assert get_cli_task_result in CODEX_TOOLS
    assert cancel_cli_task in CODEX_TOOLS
    assert list_cli_tasks in CODEX_TOOLS
    assert submit_batch_tasks in CODEX_TOOLS
    assert get_batch_status in CODEX_TOOLS


def test_cli_task_config_settings():
    """Test CLI task configuration settings."""
    from core.config import settings

    assert settings.cli_task_output_dir is not None
    assert settings.cli_task_default_timeout >= 60
    assert settings.cli_task_max_concurrent >= 1
    assert settings.cli_task_max_retries >= 0
    assert settings.cli_task_cleanup_days >= 1


def test_cli_task_repr():
    """Test CLITask __repr__ method."""
    from models import CLITask, CLITaskStatus, CLITaskType

    task = CLITask(
        name="Test Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls",
        status=CLITaskStatus.PENDING,
    )

    repr_str = repr(task)
    assert "CLITask" in repr_str
    assert "Test Task" in repr_str
    assert "shell_command" in repr_str
    assert "pending" in repr_str


def test_cli_task_input_output_data():
    """Test CLITask input and output data fields."""
    from models import CLITask, CLITaskType

    input_data = {
        "method": "chain_ladder",
        "triangles": ["paid", "incurred"],
        "periods": 12,
    }

    task = CLITask(
        name="Reserve Calculation",
        task_type=CLITaskType.RESERVE_CALCULATION,
        command="calculate_reserves.py",
        input_data=input_data,
    )

    assert task.input_data == input_data
    assert task.input_data["method"] == "chain_ladder"

    # Simulate completion with output
    output_data = {
        "ultimate_reserves": 1500000,
        "ibnr": 350000,
        "confidence_interval": [1400000, 1600000],
    }
    task.output_data = output_data

    assert task.output_data["ultimate_reserves"] == 1500000


def test_cli_task_environment_vars():
    """Test CLITask environment variables."""
    from models import CLITask, CLITaskType

    env_vars = {
        "API_KEY": "secret123",
        "LOG_LEVEL": "DEBUG",
        "OUTPUT_DIR": "/tmp/output",
    }

    task = CLITask(
        name="Task with ENV",
        task_type=CLITaskType.CUSTOM_SCRIPT,
        command="custom_script.py",
        environment_vars=env_vars,
    )

    assert task.environment_vars == env_vars
    assert task.environment_vars["API_KEY"] == "secret123"


def test_cli_task_file_paths():
    """Test CLITask input/output file paths."""
    from models import CLITask, CLITaskType

    task = CLITask(
        name="File Processing Task",
        task_type=CLITaskType.DATA_TRANSFORMATION,
        command="transform.py",
        input_file_path="/data/input/claims.csv",
        working_directory="/data/processing",
    )

    assert task.input_file_path == "/data/input/claims.csv"
    assert task.working_directory == "/data/processing"

    # Simulate completion with output file
    task.output_file_path = "/data/output/transformed_claims.csv"
    assert task.output_file_path == "/data/output/transformed_claims.csv"


def test_cli_task_metadata():
    """Test CLITask extra metadata."""
    from models import CLITask, CLITaskType

    metadata = {
        "source": "scheduled_job",
        "run_id": "run_2024_q4",
        "version": "1.2.3",
    }

    task = CLITask(
        name="Metadata Task",
        task_type=CLITaskType.SHELL_COMMAND,
        command="ls",
        extra_metadata=metadata,
    )

    assert task.extra_metadata == metadata
    assert task.extra_metadata["source"] == "scheduled_job"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
