"""Initial database schema for AI Actuary

Revision ID: 001
Revises:
Create Date: 2024-12-30 21:00:00.000000

Creates the core tables for:
- Sessions and chat messages
- Audit logs
- Engagements
- Workflow runs
- Artefacts
- Approvals
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create enum types
    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system', 'tool')")
    op.execute("""
        CREATE TYPE audit_action AS ENUM (
            'login', 'logout', 'password_change',
            'session_create', 'session_delete',
            'engagement_create', 'engagement_update', 'engagement_delete', 'engagement_archive',
            'workflow_start', 'workflow_complete', 'workflow_fail', 'workflow_cancel',
            'artefact_create', 'artefact_access', 'artefact_delete',
            'approval_request', 'approval_approve', 'approval_reject', 'approval_revoke',
            'agent_invoke', 'agent_complete', 'agent_error',
            'data_export', 'data_import',
            'settings_change', 'permission_change'
        )
    """)
    op.execute("CREATE TYPE audit_severity AS ENUM ('info', 'warning', 'error', 'critical')")
    op.execute("""
        CREATE TYPE engagement_status AS ENUM (
            'draft', 'active', 'on_hold', 'completed', 'archived', 'cancelled'
        )
    """)
    op.execute("""
        CREATE TYPE engagement_type AS ENUM (
            'reserving', 'ifrs17', 'alm', 'reinsurance',
            'pricing', 'valuation', 'review', 'advisory', 'other'
        )
    """)
    op.execute("""
        CREATE TYPE workflow_type AS ENUM (
            'data_ingestion', 'data_validation', 'data_transformation',
            'reserve_calculation', 'triangle_analysis', 'ibnr_estimation',
            'ifrs17_measurement', 'csm_calculation', 'cohort_grouping',
            'alm_analysis', 'cashflow_projection', 'duration_matching',
            'reinsurance_analysis', 'treaty_calculation', 'recoveries_calculation',
            'report_generation', 'dashboard_update',
            'quality_check', 'peer_review', 'sign_off',
            'custom'
        )
    """)
    op.execute("""
        CREATE TYPE workflow_status AS ENUM (
            'pending', 'queued', 'running', 'paused',
            'waiting_approval', 'completed', 'failed', 'cancelled'
        )
    """)
    op.execute("""
        CREATE TYPE artefact_type AS ENUM (
            'data_file', 'csv', 'excel', 'parquet',
            'report', 'pdf', 'word', 'markdown',
            'chart', 'dashboard', 'graph',
            'model_output', 'triangle', 'projection', 'sensitivity',
            'notebook', 'script',
            'log', 'metadata', 'config',
            'archive', 'other'
        )
    """)
    op.execute("""
        CREATE TYPE artefact_status AS ENUM (
            'draft', 'pending_review', 'approved', 'rejected', 'superseded', 'archived'
        )
    """)
    op.execute("""
        CREATE TYPE approval_type AS ENUM (
            'artefact_review', 'report_sign_off', 'data_validation',
            'workflow_approval', 'methodology_approval',
            'actuarial_sign_off', 'peer_review', 'final_sign_off',
            'release_approval', 'exception_approval'
        )
    """)
    op.execute("""
        CREATE TYPE approval_status AS ENUM (
            'pending', 'approved', 'rejected', 'revoked', 'expired'
        )
    """)

    # Create engagements table first (referenced by others)
    op.create_table(
        "engagements",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_code", sa.String(50), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("engagement_type", postgresql.ENUM("reserving", "ifrs17", "alm", "reinsurance", "pricing", "valuation", "review", "advisory", "other", name="engagement_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "active", "on_hold", "completed", "archived", "cancelled", name="engagement_status", create_type=False), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("lead_actuary_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagements")),
    )
    op.create_index(op.f("ix_engagements_client_code"), "engagements", ["client_code"], unique=False)
    op.create_index(op.f("ix_engagements_created_at"), "engagements", ["created_at"], unique=False)
    op.create_index(op.f("ix_engagements_created_by"), "engagements", ["created_by"], unique=False)
    op.create_index(op.f("ix_engagements_due_date"), "engagements", ["due_date"], unique=False)
    op.create_index(op.f("ix_engagements_engagement_type"), "engagements", ["engagement_type"], unique=False)
    op.create_index(op.f("ix_engagements_is_deleted"), "engagements", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_engagements_lead_actuary_id"), "engagements", ["lead_actuary_id"], unique=False)
    op.create_index(op.f("ix_engagements_reviewer_id"), "engagements", ["reviewer_id"], unique=False)
    op.create_index(op.f("ix_engagements_status"), "engagements", ["status"], unique=False)

    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, comment="Reference to Supabase auth.users.id"),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=True, comment="User-defined or auto-generated session title"),
        sa.Column("context", postgresql.JSONB(), nullable=True, comment="Session context including active agent, preferences"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], name=op.f("fk_sessions_engagement_id_engagements"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_created_at"), "sessions", ["created_at"], unique=False)
    op.create_index(op.f("ix_sessions_created_by"), "sessions", ["created_by"], unique=False)
    op.create_index(op.f("ix_sessions_engagement_id"), "sessions", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_sessions_is_deleted"), "sessions", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_sessions_last_activity_at"), "sessions", ["last_activity_at"], unique=False)
    op.create_index(op.f("ix_sessions_trace_id"), "sessions", ["trace_id"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", postgresql.ENUM("user", "assistant", "system", "tool", name="message_role", create_type=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(255), nullable=True, comment="Name of the tool called (for role=tool messages)"),
        sa.Column("tool_call_id", sa.String(255), nullable=True, comment="Tool call ID linking request and response"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional metadata: model, tokens, latency, etc."),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["chat_messages.id"], name=op.f("fk_chat_messages_parent_id_chat_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name=op.f("fk_chat_messages_session_id_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(op.f("ix_chat_messages_created_at"), "chat_messages", ["created_at"], unique=False)
    op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_chat_messages_trace_id"), "chat_messages", ["trace_id"], unique=False)

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, comment="User who performed the action (null for system actions)"),
        sa.Column("action", postgresql.ENUM("login", "logout", "password_change", "session_create", "session_delete", "engagement_create", "engagement_update", "engagement_delete", "engagement_archive", "workflow_start", "workflow_complete", "workflow_fail", "workflow_cancel", "artefact_create", "artefact_access", "artefact_delete", "approval_request", "approval_approve", "approval_reject", "approval_revoke", "agent_invoke", "agent_complete", "agent_error", "data_export", "data_import", "settings_change", "permission_change", name="audit_action", create_type=False), nullable=False),
        sa.Column("severity", postgresql.ENUM("info", "warning", "error", "critical", name="audit_severity", create_type=False), server_default=sa.text("'info'"), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False, comment="Type of resource acted upon"),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True, comment="ID of the resource acted upon"),
        sa.Column("description", sa.Text(), nullable=False, comment="Human-readable description of the action"),
        sa.Column("old_value", postgresql.JSONB(), nullable=True, comment="Previous state before the action"),
        sa.Column("new_value", postgresql.JSONB(), nullable=True, comment="New state after the action"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional context: agent name, model, tokens, etc."),
        sa.Column("ip_address", postgresql.INET(), nullable=True, comment="Client IP address"),
        sa.Column("user_agent", sa.String(500), nullable=True, comment="Client user agent string"),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Session where the action occurred"),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Engagement context for the action"),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_logs_engagement_id"), "audit_logs", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource_id"), "audit_logs", ["resource_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_session_id"), "audit_logs", ["session_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_severity"), "audit_logs", ["severity"], unique=False)
    op.create_index(op.f("ix_audit_logs_trace_id"), "audit_logs", ["trace_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)

    # Create workflow_runs table
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_type", postgresql.ENUM("data_ingestion", "data_validation", "data_transformation", "reserve_calculation", "triangle_analysis", "ibnr_estimation", "ifrs17_measurement", "csm_calculation", "cohort_grouping", "alm_analysis", "cashflow_projection", "duration_matching", "reinsurance_analysis", "treaty_calculation", "recoveries_calculation", "report_generation", "dashboard_update", "quality_check", "peer_review", "sign_off", "custom", name="workflow_type", create_type=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, comment="Descriptive name for this workflow run"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("period", sa.String(50), nullable=True, comment="Reporting/valuation period"),
        sa.Column("status", postgresql.ENUM("pending", "queued", "running", "paused", "waiting_approval", "completed", "failed", "cancelled", name="workflow_status", create_type=False), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False, default=0, comment="Total number of steps in the workflow"),
        sa.Column("current_step", sa.Integer(), nullable=False, default=0, comment="Current step being executed"),
        sa.Column("input_params", postgresql.JSONB(), nullable=True, comment="Input parameters for the workflow"),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True, comment="Summary of workflow outputs and results"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="Error message if workflow failed"),
        sa.Column("error_details", postgresql.JSONB(), nullable=True, comment="Detailed error information including stack trace"),
        sa.Column("agent_name", sa.String(100), nullable=True, comment="Name of the agent that executed this workflow"),
        sa.Column("metrics", postgresql.JSONB(), nullable=True, comment="Execution metrics: duration, tokens, api calls, etc."),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], name=op.f("fk_workflow_runs_engagement_id_engagements"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
    )
    op.create_index(op.f("ix_workflow_runs_agent_name"), "workflow_runs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_workflow_runs_created_at"), "workflow_runs", ["created_at"], unique=False)
    op.create_index(op.f("ix_workflow_runs_created_by"), "workflow_runs", ["created_by"], unique=False)
    op.create_index(op.f("ix_workflow_runs_engagement_id"), "workflow_runs", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_is_deleted"), "workflow_runs", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_workflow_runs_period"), "workflow_runs", ["period"], unique=False)
    op.create_index(op.f("ix_workflow_runs_status"), "workflow_runs", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_runs_trace_id"), "workflow_runs", ["trace_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_workflow_type"), "workflow_runs", ["workflow_type"], unique=False)

    # Create artefacts table
    op.create_table(
        "artefacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artefact_type", postgresql.ENUM("data_file", "csv", "excel", "parquet", "report", "pdf", "word", "markdown", "chart", "dashboard", "graph", "model_output", "triangle", "projection", "sensitivity", "notebook", "script", "log", "metadata", "config", "archive", "other", name="artefact_type", create_type=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, comment="Display name for the artefact"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False, comment="Original filename"),
        sa.Column("mime_type", sa.String(100), nullable=False, comment="MIME type of the file"),
        sa.Column("file_size", sa.BigInteger(), nullable=False, comment="File size in bytes"),
        sa.Column("storage_path", sa.String(1000), nullable=False, comment="Path in Supabase Storage"),
        sa.Column("storage_bucket", sa.String(100), nullable=False, default="artefacts", comment="Supabase Storage bucket name"),
        sa.Column("content_hash", sa.String(64), nullable=False, comment="SHA-256 hash of file content for integrity verification"),
        sa.Column("status", postgresql.ENUM("draft", "pending_review", "approved", "rejected", "superseded", "archived", name="artefact_status", create_type=False), nullable=False, default="draft"),
        sa.Column("version", sa.BigInteger(), nullable=False, default=1, comment="Version number for the artefact"),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Reference to the previous version of this artefact"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional metadata: tags, properties, etc."),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], name=op.f("fk_artefacts_engagement_id_engagements"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_version_id"], ["artefacts.id"], name=op.f("fk_artefacts_previous_version_id_artefacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], name=op.f("fk_artefacts_workflow_run_id_workflow_runs"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artefacts")),
    )
    op.create_index(op.f("ix_artefacts_artefact_type"), "artefacts", ["artefact_type"], unique=False)
    op.create_index(op.f("ix_artefacts_content_hash"), "artefacts", ["content_hash"], unique=False)
    op.create_index(op.f("ix_artefacts_created_at"), "artefacts", ["created_at"], unique=False)
    op.create_index(op.f("ix_artefacts_created_by"), "artefacts", ["created_by"], unique=False)
    op.create_index(op.f("ix_artefacts_engagement_id"), "artefacts", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_artefacts_is_deleted"), "artefacts", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_artefacts_status"), "artefacts", ["status"], unique=False)
    op.create_index(op.f("ix_artefacts_trace_id"), "artefacts", ["trace_id"], unique=False)
    op.create_index(op.f("ix_artefacts_workflow_run_id"), "artefacts", ["workflow_run_id"], unique=False)

    # Create approvals table
    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("artefact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_type", postgresql.ENUM("artefact_review", "report_sign_off", "data_validation", "workflow_approval", "methodology_approval", "actuarial_sign_off", "peer_review", "final_sign_off", "release_approval", "exception_approval", name="approval_type", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "approved", "rejected", "revoked", "expired", name="approval_status", create_type=False), nullable=False, default="pending"),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False, comment="User who requested the approval"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_notes", sa.Text(), nullable=True, comment="Notes from the requestor"),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), nullable=True, comment="User who approved/rejected"),
        sa.Column("designated_approver_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Specific user designated to approve"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True, comment="Notes from the approver explaining the decision"),
        sa.Column("rejection_reason", sa.String(255), nullable=True, comment="Standardized rejection reason code"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True, comment="Additional approval context and metadata"),
        sa.Column("approver_qualifications", postgresql.JSONB(), nullable=True, comment="Approver's professional qualifications at decision time"),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.ForeignKeyConstraint(["artefact_id"], ["artefacts.id"], name=op.f("fk_approvals_artefact_id_artefacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], name=op.f("fk_approvals_engagement_id_engagements"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
    )
    op.create_index(op.f("ix_approvals_approval_type"), "approvals", ["approval_type"], unique=False)
    op.create_index(op.f("ix_approvals_approver_id"), "approvals", ["approver_id"], unique=False)
    op.create_index(op.f("ix_approvals_artefact_id"), "approvals", ["artefact_id"], unique=False)
    op.create_index(op.f("ix_approvals_designated_approver_id"), "approvals", ["designated_approver_id"], unique=False)
    op.create_index(op.f("ix_approvals_engagement_id"), "approvals", ["engagement_id"], unique=False)
    op.create_index(op.f("ix_approvals_expires_at"), "approvals", ["expires_at"], unique=False)
    op.create_index(op.f("ix_approvals_requested_by"), "approvals", ["requested_by"], unique=False)
    op.create_index(op.f("ix_approvals_status"), "approvals", ["status"], unique=False)
    op.create_index(op.f("ix_approvals_trace_id"), "approvals", ["trace_id"], unique=False)


def downgrade() -> None:
    """Drop all tables and types."""
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table("approvals")
    op.drop_table("artefacts")
    op.drop_table("workflow_runs")
    op.drop_table("audit_logs")
    op.drop_table("chat_messages")
    op.drop_table("sessions")
    op.drop_table("engagements")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS approval_status")
    op.execute("DROP TYPE IF EXISTS approval_type")
    op.execute("DROP TYPE IF EXISTS artefact_status")
    op.execute("DROP TYPE IF EXISTS artefact_type")
    op.execute("DROP TYPE IF EXISTS workflow_status")
    op.execute("DROP TYPE IF EXISTS workflow_type")
    op.execute("DROP TYPE IF EXISTS engagement_type")
    op.execute("DROP TYPE IF EXISTS engagement_status")
    op.execute("DROP TYPE IF EXISTS audit_severity")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS message_role")
