"""
Tests for SQLAlchemy models.

Verifies that all models are properly defined and can be imported.
Tests model instantiation, relationships, and helper methods.
"""

import pytest
from datetime import date, datetime
from uuid import uuid4

# Test model imports
def test_model_imports():
    """Verify all models can be imported."""
    from models import (
        Approval,
        ApprovalStatus,
        Artefact,
        ArtefactType,
        AuditLog,
        AuditAction,
        ChatMessage,
        Engagement,
        EngagementStatus,
        Session,
        WorkflowRun,
        WorkflowStatus,
        WorkflowType,
        UUIDMixin,
        TimestampMixin,
        AuditMixin,
        SoftDeleteMixin,
    )

    # All imports should succeed
    assert Approval is not None
    assert Artefact is not None
    assert AuditLog is not None
    assert ChatMessage is not None
    assert Engagement is not None
    assert Session is not None
    assert WorkflowRun is not None


def test_base_imports():
    """Verify base mixins can be imported."""
    from models.base import (
        UUIDMixin,
        TimestampMixin,
        AuditMixin,
        SoftDeleteMixin,
        TraceableMixin,
    )

    assert UUIDMixin is not None
    assert TimestampMixin is not None
    assert AuditMixin is not None
    assert SoftDeleteMixin is not None
    assert TraceableMixin is not None


def test_database_imports():
    """Verify database module can be imported."""
    from core.database import (
        Base,
        get_db,
        get_db_context,
        get_session_factory,
        get_engine,
        init_db,
        close_db,
    )

    assert Base is not None
    assert get_engine is not None
    assert get_session_factory is not None


def test_engagement_status_enum():
    """Test EngagementStatus enum values."""
    from models import EngagementStatus

    assert EngagementStatus.DRAFT.value == "draft"
    assert EngagementStatus.ACTIVE.value == "active"
    assert EngagementStatus.COMPLETED.value == "completed"
    assert EngagementStatus.ARCHIVED.value == "archived"


def test_workflow_status_enum():
    """Test WorkflowStatus enum values."""
    from models import WorkflowStatus

    assert WorkflowStatus.PENDING.value == "pending"
    assert WorkflowStatus.RUNNING.value == "running"
    assert WorkflowStatus.COMPLETED.value == "completed"
    assert WorkflowStatus.FAILED.value == "failed"


def test_workflow_type_enum():
    """Test WorkflowType enum values."""
    from models import WorkflowType

    assert WorkflowType.DATA_INGESTION.value == "data_ingestion"
    assert WorkflowType.RESERVE_CALCULATION.value == "reserve_calculation"
    assert WorkflowType.IFRS17_MEASUREMENT.value == "ifrs17_measurement"


def test_artefact_type_enum():
    """Test ArtefactType enum values."""
    from models import ArtefactType

    assert ArtefactType.REPORT.value == "report"
    assert ArtefactType.CSV.value == "csv"
    assert ArtefactType.EXCEL.value == "excel"


def test_approval_status_enum():
    """Test ApprovalStatus enum values."""
    from models import ApprovalStatus

    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"


def test_audit_action_enum():
    """Test AuditAction enum values."""
    from models import AuditAction

    assert AuditAction.LOGIN.value == "login"
    assert AuditAction.ENGAGEMENT_CREATE.value == "engagement_create"
    assert AuditAction.WORKFLOW_START.value == "workflow_start"


def test_engagement_model_instantiation():
    """Test Engagement model can be instantiated."""
    from models import Engagement, EngagementStatus
    from models.engagement import EngagementType

    engagement = Engagement(
        client_code="TEST001",
        client_name="Test Client",
        name="Test Engagement",
        engagement_type=EngagementType.RESERVING,
        status=EngagementStatus.DRAFT,
    )

    assert engagement.client_code == "TEST001"
    assert engagement.client_name == "Test Client"
    assert engagement.is_editable is True


def test_engagement_status_transitions():
    """Test Engagement status transition methods."""
    from models import Engagement, EngagementStatus
    from models.engagement import EngagementType

    engagement = Engagement(
        client_code="TEST001",
        client_name="Test Client",
        name="Test Engagement",
        engagement_type=EngagementType.RESERVING,
        status=EngagementStatus.DRAFT,
    )

    # Test activate
    engagement.activate()
    assert engagement.status == EngagementStatus.ACTIVE

    # Test complete
    engagement.complete()
    assert engagement.status == EngagementStatus.COMPLETED

    # Test archive
    engagement.archive()
    assert engagement.status == EngagementStatus.ARCHIVED


def test_workflow_run_model_instantiation():
    """Test WorkflowRun model can be instantiated."""
    from models import WorkflowRun, WorkflowStatus, WorkflowType

    workflow = WorkflowRun(
        engagement_id=uuid4(),
        workflow_type=WorkflowType.RESERVE_CALCULATION,
        name="Q4 Reserve Calculation",
        status=WorkflowStatus.PENDING,
        period="2024-Q4",
    )

    assert workflow.name == "Q4 Reserve Calculation"
    assert workflow.period == "2024-Q4"
    assert workflow.progress_percent == 0.0


def test_workflow_progress_percent_bounds():
    """Test progress_percent is clamped between 0 and 100."""
    from models import WorkflowRun, WorkflowStatus, WorkflowType

    workflow = WorkflowRun(
        engagement_id=uuid4(),
        workflow_type=WorkflowType.RESERVE_CALCULATION,
        name="Test Workflow",
        status=WorkflowStatus.RUNNING,
        step_count=10,
        current_step=5,
    )

    # Normal case: 50%
    assert workflow.progress_percent == 50.0

    # Edge case: current_step > step_count (should clamp to 100)
    workflow.current_step = 15
    assert workflow.progress_percent == 100.0

    # Edge case: negative current_step (should clamp to 0)
    workflow.current_step = -5
    assert workflow.progress_percent == 0.0

    # Edge case: step_count is 0 (should return 0)
    workflow.step_count = 0
    assert workflow.progress_percent == 0.0


def test_workflow_run_lifecycle():
    """Test WorkflowRun lifecycle methods."""
    from models import WorkflowRun, WorkflowStatus, WorkflowType

    workflow = WorkflowRun(
        engagement_id=uuid4(),
        workflow_type=WorkflowType.RESERVE_CALCULATION,
        name="Test Workflow",
        status=WorkflowStatus.PENDING,
    )

    # Test start
    workflow.start()
    assert workflow.status == WorkflowStatus.RUNNING
    assert workflow.started_at is not None

    # Test complete
    workflow.complete({"result": "success"})
    assert workflow.status == WorkflowStatus.COMPLETED
    assert workflow.completed_at is not None
    assert workflow.output_summary == {"result": "success"}


def test_artefact_model_instantiation():
    """Test Artefact model can be instantiated."""
    from models import Artefact, ArtefactType
    from models.artefact import ArtefactStatus

    artefact = Artefact(
        engagement_id=uuid4(),
        artefact_type=ArtefactType.REPORT,
        name="Q4 Reserve Report",
        file_name="reserve_report_2024q4.pdf",
        mime_type="application/pdf",
        file_size=1024000,
        storage_path="engagements/123/reports/reserve_report_2024q4.pdf",
        content_hash="abc123def456",
        status=ArtefactStatus.DRAFT,
    )

    assert artefact.name == "Q4 Reserve Report"
    assert artefact.is_approved is False
    assert artefact.requires_approval is False


def test_artefact_approval_workflow():
    """Test Artefact approval workflow methods."""
    from models import Artefact, ArtefactType
    from models.artefact import ArtefactStatus

    artefact = Artefact(
        engagement_id=uuid4(),
        artefact_type=ArtefactType.REPORT,
        name="Test Report",
        file_name="test.pdf",
        mime_type="application/pdf",
        file_size=1024,
        storage_path="test/test.pdf",
        content_hash="hash123",
        status=ArtefactStatus.DRAFT,
    )

    # Submit for review
    artefact.submit_for_review()
    assert artefact.status == ArtefactStatus.PENDING_REVIEW
    assert artefact.requires_approval is True

    # Approve
    artefact.approve()
    assert artefact.status == ArtefactStatus.APPROVED
    assert artefact.is_approved is True


def test_approval_model_instantiation():
    """Test Approval model can be instantiated."""
    from models import Approval, ApprovalStatus
    from models.approval import ApprovalType

    approval = Approval(
        artefact_id=uuid4(),
        approval_type=ApprovalType.ACTUARIAL_SIGN_OFF,
        status=ApprovalStatus.PENDING,
        requested_by=uuid4(),
    )

    assert approval.is_pending is True
    assert approval.is_approved is False


def test_approval_lifecycle():
    """Test Approval lifecycle methods."""
    from models import Approval, ApprovalStatus
    from models.approval import ApprovalType

    approval = Approval(
        artefact_id=uuid4(),
        approval_type=ApprovalType.ACTUARIAL_SIGN_OFF,
        status=ApprovalStatus.PENDING,
        requested_by=uuid4(),
    )

    approver_id = uuid4()

    # Approve
    approval.approve(approver_id, notes="Looks good", qualifications={"designation": "FASSA"})
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approver_id == approver_id
    assert approval.approver_qualifications == {"designation": "FASSA"}


def test_audit_log_factory():
    """Test AuditLog.create factory method."""
    from models import AuditLog, AuditAction
    from models.audit import AuditSeverity

    log = AuditLog.create(
        action=AuditAction.ENGAGEMENT_CREATE,
        resource_type="engagement",
        description="Created new engagement for Test Client",
        user_id=uuid4(),
        resource_id=uuid4(),
        new_value={"name": "Test Engagement"},
        severity=AuditSeverity.INFO,
    )

    assert log.action == AuditAction.ENGAGEMENT_CREATE
    assert log.resource_type == "engagement"
    assert log.severity == AuditSeverity.INFO


def test_session_model_instantiation():
    """Test Session model can be instantiated."""
    from models import Session

    session = Session(
        user_id=uuid4(),
        title="Test Session",
        context={"active_agent": "engagement_manager"},
    )

    assert session.title == "Test Session"
    assert session.context == {"active_agent": "engagement_manager"}


def test_chat_message_model():
    """Test ChatMessage model can be instantiated."""
    from models import ChatMessage
    from models.session import MessageRole

    message = ChatMessage(
        session_id=uuid4(),
        role=MessageRole.USER,
        content="Hello, can you help me with reserve calculations?",
        message_metadata={"model": "gpt-4o"},
    )

    assert message.role == MessageRole.USER
    assert "reserve calculations" in message.content
    assert message.message_metadata == {"model": "gpt-4o"}


def test_chat_message_all_roles():
    """Test ChatMessage model with all role types."""
    from models import ChatMessage
    from models.session import MessageRole

    session_id = uuid4()

    # Test USER role
    user_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        content="User message",
    )
    assert user_msg.role == MessageRole.USER
    assert user_msg.role.value == "user"

    # Test ASSISTANT role
    assistant_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content="Assistant response",
        message_metadata={"model": "gpt-4o", "tokens": 150},
    )
    assert assistant_msg.role == MessageRole.ASSISTANT
    assert assistant_msg.role.value == "assistant"
    assert assistant_msg.message_metadata["tokens"] == 150

    # Test SYSTEM role
    system_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.SYSTEM,
        content="System instructions",
    )
    assert system_msg.role == MessageRole.SYSTEM
    assert system_msg.role.value == "system"

    # Test TOOL role
    tool_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.TOOL,
        content='{"result": "success"}',
        tool_name="calculate_reserves",
        tool_call_id="call_abc123",
    )
    assert tool_msg.role == MessageRole.TOOL
    assert tool_msg.role.value == "tool"
    assert tool_msg.tool_name == "calculate_reserves"
    assert tool_msg.tool_call_id == "call_abc123"


def test_chat_message_parent_threading():
    """Test ChatMessage parent-child relationship for threading."""
    from models import ChatMessage
    from models.session import MessageRole

    session_id = uuid4()
    parent_id = uuid4()

    # Create a child message with parent reference
    child_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content="Follow-up response",
        parent_id=parent_id,
    )
    assert child_msg.parent_id == parent_id


def test_chat_message_trace_id():
    """Test ChatMessage trace_id for OpenAI Agents SDK integration."""
    from models import ChatMessage
    from models.session import MessageRole

    trace_id = "trace_abc123xyz"
    message = ChatMessage(
        session_id=uuid4(),
        role=MessageRole.USER,
        content="Test message",
        trace_id=trace_id,
    )
    assert message.trace_id == trace_id


def test_soft_delete_mixin():
    """Test SoftDeleteMixin functionality."""
    from models import Engagement, EngagementStatus
    from models.engagement import EngagementType

    engagement = Engagement(
        client_code="TEST001",
        client_name="Test Client",
        name="Test Engagement",
        engagement_type=EngagementType.RESERVING,
        status=EngagementStatus.DRAFT,
    )

    # Initially not deleted
    assert engagement.is_deleted is False
    assert engagement.deleted_at is None

    # Soft delete
    user_id = uuid4()
    engagement.soft_delete(user_id)
    assert engagement.is_deleted is True
    assert engagement.deleted_at is not None
    assert engagement.deleted_by == user_id

    # Restore
    engagement.restore()
    assert engagement.is_deleted is False
    assert engagement.deleted_at is None
    assert engagement.deleted_by is None


def test_config_settings():
    """Test database settings in config."""
    from core.config import settings

    assert settings.database_url is not None
    assert "postgresql" in settings.database_url
    assert settings.database_pool_size >= 1


def test_backup_model_imports():
    """Test backup model imports."""
    from models import (
        Backup,
        BackupStatus,
        BackupType,
        Recovery,
        RecoveryStatus,
    )

    assert Backup is not None
    assert BackupStatus is not None
    assert BackupType is not None
    assert Recovery is not None
    assert RecoveryStatus is not None


def test_backup_status_enum():
    """Test BackupStatus enum values."""
    from models import BackupStatus

    assert BackupStatus.PENDING.value == "pending"
    assert BackupStatus.IN_PROGRESS.value == "in_progress"
    assert BackupStatus.COMPLETED.value == "completed"
    assert BackupStatus.FAILED.value == "failed"
    assert BackupStatus.CANCELLED.value == "cancelled"
    assert BackupStatus.EXPIRED.value == "expired"


def test_backup_type_enum():
    """Test BackupType enum values."""
    from models import BackupType

    assert BackupType.FULL.value == "full"
    assert BackupType.INCREMENTAL.value == "incremental"
    assert BackupType.DIFFERENTIAL.value == "differential"
    assert BackupType.AUDIT_LOGS.value == "audit_logs"
    assert BackupType.ARTEFACTS.value == "artefacts"
    assert BackupType.ENGAGEMENT.value == "engagement"


def test_recovery_status_enum():
    """Test RecoveryStatus enum values."""
    from models import RecoveryStatus

    assert RecoveryStatus.PENDING.value == "pending"
    assert RecoveryStatus.IN_PROGRESS.value == "in_progress"
    assert RecoveryStatus.COMPLETED.value == "completed"
    assert RecoveryStatus.FAILED.value == "failed"
    assert RecoveryStatus.ROLLED_BACK.value == "rolled_back"


def test_backup_model_instantiation():
    """Test Backup model can be instantiated."""
    from models import Backup, BackupStatus, BackupType

    backup = Backup(
        name="Test Backup",
        description="Test backup description",
        backup_type=BackupType.FULL,
        status=BackupStatus.PENDING,
        storage_provider="local",
    )

    assert backup.name == "Test Backup"
    assert backup.backup_type == BackupType.FULL
    assert backup.status == BackupStatus.PENDING


def test_backup_lifecycle():
    """Test Backup lifecycle methods."""
    from models import Backup, BackupStatus, BackupType

    backup = Backup(
        name="Test Backup",
        backup_type=BackupType.FULL,
        status=BackupStatus.PENDING,
    )

    # Test start
    backup.start()
    assert backup.status == BackupStatus.IN_PROGRESS
    assert backup.started_at is not None

    # Test complete
    backup.complete(
        storage_path="/tmp/backup.json",
        file_size_bytes=1024,
        record_count=10,
        checksum="abc123",
    )
    assert backup.status == BackupStatus.COMPLETED
    assert backup.completed_at is not None
    assert backup.storage_path == "/tmp/backup.json"
    assert backup.file_size_bytes == 1024
    assert backup.record_count == 10
    assert backup.checksum == "abc123"


def test_backup_failure():
    """Test Backup failure handling."""
    from models import Backup, BackupStatus, BackupType

    backup = Backup(
        name="Test Backup",
        backup_type=BackupType.FULL,
        status=BackupStatus.PENDING,
    )

    backup.start()
    backup.fail("Connection error")

    assert backup.status == BackupStatus.FAILED
    assert backup.error_message == "Connection error"
    assert backup.completed_at is not None


def test_recovery_model_instantiation():
    """Test Recovery model can be instantiated."""
    from models import Recovery, RecoveryStatus

    recovery = Recovery(
        name="Test Recovery",
        description="Test recovery description",
        backup_id=uuid4(),
        status=RecoveryStatus.PENDING,
    )

    assert recovery.name == "Test Recovery"
    assert recovery.status == RecoveryStatus.PENDING


def test_recovery_lifecycle():
    """Test Recovery lifecycle methods."""
    from models import Recovery, RecoveryStatus

    recovery = Recovery(
        name="Test Recovery",
        backup_id=uuid4(),
        status=RecoveryStatus.PENDING,
    )

    # Test start
    recovery.start()
    assert recovery.status == RecoveryStatus.IN_PROGRESS
    assert recovery.started_at is not None

    # Test complete
    recovery.complete(["sessions", "engagements"], 25)
    assert recovery.status == RecoveryStatus.COMPLETED
    assert recovery.completed_at is not None
    assert recovery.tables_recovered == ["sessions", "engagements"]
    assert recovery.records_recovered == 25


def test_recovery_failure():
    """Test Recovery failure handling."""
    from models import Recovery, RecoveryStatus

    recovery = Recovery(
        name="Test Recovery",
        backup_id=uuid4(),
        status=RecoveryStatus.PENDING,
    )

    recovery.start()
    recovery.fail("Restore error")

    assert recovery.status == RecoveryStatus.FAILED
    assert recovery.error_message == "Restore error"


def test_recovery_rollback():
    """Test Recovery rollback handling."""
    from models import Recovery, RecoveryStatus

    recovery = Recovery(
        name="Test Recovery",
        backup_id=uuid4(),
        status=RecoveryStatus.PENDING,
    )

    recovery.start()
    recovery.complete(["sessions"], 10)
    recovery.rollback()

    assert recovery.status == RecoveryStatus.ROLLED_BACK


def test_backup_config_settings():
    """Test backup settings in config."""
    from core.config import settings

    assert settings.backup_dir is not None
    assert settings.backup_retention_days >= 1
    assert settings.backup_max_file_size_mb >= 1


def test_backup_service_import():
    """Test backup service can be imported."""
    from services import BackupService, get_backup_service

    assert BackupService is not None
    assert get_backup_service is not None


def test_recovery_service_import():
    """Test recovery service can be imported."""
    from services import RecoveryService, get_recovery_service

    assert RecoveryService is not None
    assert get_recovery_service is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
