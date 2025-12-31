#!/usr/bin/env python3
"""
Schema verification script for the AI Actuary database.

This script verifies that all models are properly defined and can be loaded.
It performs static analysis without requiring a database connection.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))


def verify_imports():
    """Verify all model imports work correctly."""
    print("Verifying model imports...")

    try:
        from models.base import (
            UUIDMixin,
            TimestampMixin,
            AuditMixin,
            SoftDeleteMixin,
            TraceableMixin,
        )
        print("  ✓ Base mixins imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import base mixins: {e}")
        return False

    try:
        from models.session import Session, ChatMessage, MessageRole
        print("  ✓ Session models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import session models: {e}")
        return False

    try:
        from models.audit import AuditLog, AuditAction, AuditSeverity
        print("  ✓ Audit models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import audit models: {e}")
        return False

    try:
        from models.engagement import Engagement, EngagementStatus, EngagementType
        print("  ✓ Engagement models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import engagement models: {e}")
        return False

    try:
        from models.workflow import WorkflowRun, WorkflowStatus, WorkflowType
        print("  ✓ Workflow models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import workflow models: {e}")
        return False

    try:
        from models.artefact import Artefact, ArtefactType, ArtefactStatus
        print("  ✓ Artefact models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import artefact models: {e}")
        return False

    try:
        from models.approval import Approval, ApprovalStatus, ApprovalType
        print("  ✓ Approval models imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import approval models: {e}")
        return False

    return True


def verify_database_config():
    """Verify database configuration is properly set up."""
    print("\nVerifying database configuration...")

    try:
        from core.config import settings
        print(f"  ✓ Settings loaded: database_url = {settings.database_url[:50]}...")
        print(f"  ✓ Pool size: {settings.database_pool_size}")
        print(f"  ✓ Pool overflow: {settings.database_pool_overflow}")
    except ImportError as e:
        print(f"  ✗ Failed to import settings: {e}")
        return False

    try:
        from core.database import Base, get_engine, get_session_factory

        # Initialize to ensure configuration is valid without connecting
        _ = get_engine()
        _ = get_session_factory()
        print("  ✓ Database module loaded successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import database module: {e}")
        return False

    return True


def verify_model_structure():
    """Verify model table definitions and relationships."""
    print("\nVerifying model structure...")

    try:
        from core.database import Base

        # Check that all expected tables are registered
        expected_tables = {
            'sessions',
            'chat_messages',
            'audit_logs',
            'engagements',
            'workflow_runs',
            'artefacts',
            'approvals',
        }

        registered_tables = set(Base.metadata.tables.keys())

        for table in expected_tables:
            if table in registered_tables:
                print(f"  ✓ Table '{table}' registered")
            else:
                print(f"  ✗ Table '{table}' NOT registered")
                return False

        # Verify foreign key relationships
        print("\nVerifying foreign key relationships...")
        for table_name, table in Base.metadata.tables.items():
            fk_count = len(table.foreign_keys)
            print(f"  - {table_name}: {fk_count} foreign key(s)")

    except Exception as e:
        print(f"  ✗ Failed to verify model structure: {e}")
        return False

    return True


def verify_enums():
    """Verify all enum definitions."""
    print("\nVerifying enum definitions...")

    enums_to_check = [
        ('models.session', 'MessageRole', ['user', 'assistant', 'system', 'tool']),
        ('models.audit', 'AuditAction', ['login', 'logout', 'engagement_create']),
        ('models.audit', 'AuditSeverity', ['info', 'warning', 'error', 'critical']),
        ('models.engagement', 'EngagementStatus', ['draft', 'active', 'completed']),
        ('models.engagement', 'EngagementType', ['reserving', 'ifrs17', 'alm']),
        ('models.workflow', 'WorkflowStatus', ['pending', 'running', 'completed', 'failed']),
        ('models.workflow', 'WorkflowType', ['data_ingestion', 'reserve_calculation']),
        ('models.artefact', 'ArtefactType', ['report', 'csv', 'excel']),
        ('models.artefact', 'ArtefactStatus', ['draft', 'approved', 'rejected']),
        ('models.approval', 'ApprovalStatus', ['pending', 'approved', 'rejected']),
        ('models.approval', 'ApprovalType', ['actuarial_sign_off', 'peer_review']),
    ]

    for module_name, enum_name, expected_values in enums_to_check:
        try:
            module = __import__(module_name, fromlist=[enum_name])
            enum_class = getattr(module, enum_name)
            actual_values = [e.value for e in enum_class]

            missing = set(expected_values) - set(actual_values)
            if missing:
                print(f"  ✗ {enum_name}: missing values {missing}")
                return False

            print(f"  ✓ {enum_name}: {len(actual_values)} values defined")
        except Exception as e:
            print(f"  ✗ Failed to verify {enum_name}: {e}")
            return False

    return True


def verify_model_methods():
    """Verify model helper methods exist and work."""
    print("\nVerifying model helper methods...")

    try:
        from uuid import uuid4
        from models.engagement import Engagement, EngagementStatus, EngagementType

        # Test engagement instantiation
        engagement = Engagement(
            client_code="TEST",
            client_name="Test Client",
            name="Test Engagement",
            engagement_type=EngagementType.RESERVING,
            status=EngagementStatus.DRAFT,
        )

        assert hasattr(engagement, 'is_active'), "Missing is_active property"
        assert hasattr(engagement, 'is_editable'), "Missing is_editable property"
        assert hasattr(engagement, 'activate'), "Missing activate method"
        assert hasattr(engagement, 'complete'), "Missing complete method"
        assert hasattr(engagement, 'archive'), "Missing archive method"
        print("  ✓ Engagement methods verified")

        from models.workflow import WorkflowRun, WorkflowStatus, WorkflowType

        workflow = WorkflowRun(
            engagement_id=uuid4(),
            workflow_type=WorkflowType.RESERVE_CALCULATION,
            name="Test",
            status=WorkflowStatus.PENDING,
        )

        assert hasattr(workflow, 'duration_seconds'), "Missing duration_seconds property"
        assert hasattr(workflow, 'progress_percent'), "Missing progress_percent property"
        assert hasattr(workflow, 'start'), "Missing start method"
        assert hasattr(workflow, 'complete'), "Missing complete method"
        assert hasattr(workflow, 'fail'), "Missing fail method"
        print("  ✓ WorkflowRun methods verified")

        from models.artefact import Artefact, ArtefactType, ArtefactStatus

        artefact = Artefact(
            engagement_id=uuid4(),
            artefact_type=ArtefactType.REPORT,
            name="Test",
            file_name="test.pdf",
            mime_type="application/pdf",
            file_size=1024,
            storage_path="test/test.pdf",
            content_hash="hash",
            status=ArtefactStatus.DRAFT,
        )

        assert hasattr(artefact, 'is_approved'), "Missing is_approved property"
        assert hasattr(artefact, 'requires_approval'), "Missing requires_approval property"
        assert hasattr(artefact, 'submit_for_review'), "Missing submit_for_review method"
        print("  ✓ Artefact methods verified")

        from models.approval import Approval, ApprovalStatus, ApprovalType

        approval = Approval(
            artefact_id=uuid4(),
            approval_type=ApprovalType.ACTUARIAL_SIGN_OFF,
            status=ApprovalStatus.PENDING,
            requested_by=uuid4(),
        )

        assert hasattr(approval, 'is_pending'), "Missing is_pending property"
        assert hasattr(approval, 'is_approved'), "Missing is_approved property"
        assert hasattr(approval, 'approve'), "Missing approve method"
        assert hasattr(approval, 'reject'), "Missing reject method"
        print("  ✓ Approval methods verified")

        from models.audit import AuditLog, AuditAction

        assert hasattr(AuditLog, 'create'), "Missing create factory method"
        print("  ✓ AuditLog factory method verified")

    except Exception as e:
        print(f"  ✗ Failed to verify model methods: {e}")
        return False

    return True


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("AI Actuary Database Schema Verification")
    print("=" * 60)

    checks = [
        ("Import Verification", verify_imports),
        ("Database Config", verify_database_config),
        ("Model Structure", verify_model_structure),
        ("Enum Definitions", verify_enums),
        ("Model Methods", verify_model_methods),
    ]

    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} check failed with exception: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All verification checks passed!")
        return 0
    else:
        print("❌ Some verification checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
