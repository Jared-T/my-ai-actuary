"""Add knowledge base tables for actuarial methods, templates, and precedents

Revision ID: 004
Revises: 003
Create Date: 2024-12-31 10:00:00.000000

Creates tables for:
- actuarial_methods: Library of actuarial methods and techniques
- templates: Document templates and report structures
- precedents: Historical cases and reference implementations
- kb_search_logs: Search analytics and improvement tracking

Also enables pgvector extension for vector similarity search.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create knowledge base tables and enable pgvector."""

    # Enable pgvector extension for vector similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create enum types for knowledge base
    op.execute("""
        CREATE TYPE kb_category AS ENUM (
            'reserving', 'ifrs17', 'alm', 'reinsurance',
            'pricing', 'valuation', 'data_quality', 'reporting',
            'regulatory', 'methodology', 'best_practice', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE kb_type AS ENUM (
            'method', 'template', 'precedent', 'reference', 'guidance'
        )
    """)

    op.execute("""
        CREATE TYPE kb_status AS ENUM (
            'draft', 'active', 'under_review', 'deprecated', 'archived'
        )
    """)

    # Create actuarial_methods table
    op.create_table(
        "actuarial_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True, comment="Method name"),
        sa.Column("code", sa.String(50), nullable=False, unique=True, comment="Short code for the method"),
        sa.Column("category", postgresql.ENUM("reserving", "ifrs17", "alm", "reinsurance", "pricing", "valuation", "data_quality", "reporting", "regulatory", "methodology", "best_practice", "other", name="kb_category", create_type=False), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, comment="Brief summary of the method"),
        sa.Column("description", sa.Text(), nullable=False, comment="Detailed description"),
        sa.Column("use_cases", sa.Text(), nullable=True, comment="Typical use cases"),
        sa.Column("mathematical_formulation", sa.Text(), nullable=True, comment="Mathematical formulas"),
        sa.Column("implementation_guidance", sa.Text(), nullable=True, comment="Implementation steps"),
        sa.Column("limitations", sa.Text(), nullable=True, comment="Known limitations"),
        sa.Column("status", postgresql.ENUM("draft", "active", "under_review", "deprecated", "archived", name="kb_status", create_type=False), server_default=sa.text("'active'"), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=True, comment="Tags for categorization"),
        sa.Column("related_standards", postgresql.ARRAY(sa.String(100)), nullable=True, comment="Related regulatory standards"),
        sa.Column("version", sa.String(20), server_default=sa.text("'1.0'"), nullable=False),
        sa.Column("search_priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("usage_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True, comment="Vector embedding as JSON array"),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="OpenAI Agents SDK trace identifier"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actuarial_methods")),
    )

    # Create indexes for actuarial_methods
    op.create_index(op.f("ix_actuarial_methods_category"), "actuarial_methods", ["category"], unique=False)
    op.create_index(op.f("ix_actuarial_methods_status"), "actuarial_methods", ["status"], unique=False)
    op.create_index(op.f("ix_actuarial_methods_created_at"), "actuarial_methods", ["created_at"], unique=False)
    op.create_index(op.f("ix_actuarial_methods_created_by"), "actuarial_methods", ["created_by"], unique=False)
    op.create_index(op.f("ix_actuarial_methods_is_deleted"), "actuarial_methods", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_actuarial_methods_trace_id"), "actuarial_methods", ["trace_id"], unique=False)
    op.create_index("ix_actuarial_methods_category_status", "actuarial_methods", ["category", "status"], unique=False)

    # Create templates table
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True, comment="Template name"),
        sa.Column("code", sa.String(50), nullable=False, unique=True, comment="Short code for the template"),
        sa.Column("template_type", postgresql.ENUM("method", "template", "precedent", "reference", "guidance", name="kb_type", create_type=False), server_default=sa.text("'template'"), nullable=False),
        sa.Column("category", postgresql.ENUM("reserving", "ifrs17", "alm", "reinsurance", "pricing", "valuation", "data_quality", "reporting", "regulatory", "methodology", "best_practice", "other", name="kb_category", create_type=False), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, comment="Brief description of the template"),
        sa.Column("description", sa.Text(), nullable=False, comment="Detailed description"),
        sa.Column("structure", postgresql.JSONB(), nullable=True, comment="Template structure definition"),
        sa.Column("required_inputs", postgresql.JSONB(), nullable=True, comment="Required data inputs"),
        sa.Column("output_format", sa.String(50), nullable=True, comment="Output format"),
        sa.Column("content", sa.Text(), nullable=True, comment="Template content"),
        sa.Column("storage_path", sa.String(1000), nullable=True, comment="Path to template file"),
        sa.Column("status", postgresql.ENUM("draft", "active", "under_review", "deprecated", "archived", name="kb_status", create_type=False), server_default=sa.text("'active'"), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("version", sa.String(20), server_default=sa.text("'1.0'"), nullable=False),
        sa.Column("search_priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("usage_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True, comment="Vector embedding as JSON array"),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_templates")),
    )

    # Create indexes for templates
    op.create_index(op.f("ix_templates_category"), "templates", ["category"], unique=False)
    op.create_index(op.f("ix_templates_template_type"), "templates", ["template_type"], unique=False)
    op.create_index(op.f("ix_templates_status"), "templates", ["status"], unique=False)
    op.create_index(op.f("ix_templates_created_at"), "templates", ["created_at"], unique=False)
    op.create_index(op.f("ix_templates_created_by"), "templates", ["created_by"], unique=False)
    op.create_index(op.f("ix_templates_is_deleted"), "templates", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_templates_trace_id"), "templates", ["trace_id"], unique=False)
    op.create_index("ix_templates_category_status", "templates", ["category", "status"], unique=False)

    # Create precedents table
    op.create_table(
        "precedents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, comment="Precedent title"),
        sa.Column("reference_code", sa.String(100), nullable=False, unique=True, comment="Unique reference code"),
        sa.Column("category", postgresql.ENUM("reserving", "ifrs17", "alm", "reinsurance", "pricing", "valuation", "data_quality", "reporting", "regulatory", "methodology", "best_practice", "other", name="kb_category", create_type=False), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, comment="Brief summary of the case"),
        sa.Column("description", sa.Text(), nullable=False, comment="Detailed case description"),
        sa.Column("context", sa.Text(), nullable=True, comment="Business context"),
        sa.Column("industry", sa.String(100), nullable=True, comment="Industry sector"),
        sa.Column("jurisdiction", sa.String(100), nullable=True, comment="Regulatory jurisdiction"),
        sa.Column("reporting_period", sa.String(50), nullable=True, comment="Reporting period"),
        sa.Column("methods_used", postgresql.ARRAY(sa.String(100)), nullable=True, comment="Actuarial methods applied"),
        sa.Column("approach_description", sa.Text(), nullable=True, comment="Approach taken"),
        sa.Column("outcome", sa.Text(), nullable=True, comment="Results and outcomes"),
        sa.Column("lessons_learned", sa.Text(), nullable=True, comment="Key lessons"),
        sa.Column("related_artefacts", postgresql.JSONB(), nullable=True, comment="Related artefact references"),
        sa.Column("status", postgresql.ENUM("draft", "active", "under_review", "deprecated", "archived", name="kb_status", create_type=False), server_default=sa.text("'active'"), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("confidentiality_level", sa.String(50), server_default=sa.text("'internal'"), nullable=False),
        sa.Column("is_anonymized", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("search_priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("usage_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("embedding", sa.Text(), nullable=True, comment="Vector embedding as JSON array"),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_precedents")),
    )

    # Create indexes for precedents
    op.create_index(op.f("ix_precedents_category"), "precedents", ["category"], unique=False)
    op.create_index(op.f("ix_precedents_status"), "precedents", ["status"], unique=False)
    op.create_index(op.f("ix_precedents_industry"), "precedents", ["industry"], unique=False)
    op.create_index(op.f("ix_precedents_jurisdiction"), "precedents", ["jurisdiction"], unique=False)
    op.create_index(op.f("ix_precedents_confidentiality_level"), "precedents", ["confidentiality_level"], unique=False)
    op.create_index(op.f("ix_precedents_created_at"), "precedents", ["created_at"], unique=False)
    op.create_index(op.f("ix_precedents_created_by"), "precedents", ["created_by"], unique=False)
    op.create_index(op.f("ix_precedents_is_deleted"), "precedents", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_precedents_trace_id"), "precedents", ["trace_id"], unique=False)
    op.create_index("ix_precedents_category_status", "precedents", ["category", "status"], unique=False)

    # Create kb_search_logs table
    op.create_table(
        "kb_search_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True, comment="User who performed the search"),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Session context"),
        sa.Column("query", sa.Text(), nullable=False, comment="Search query text"),
        sa.Column("search_type", sa.String(50), nullable=False, comment="Type of search"),
        sa.Column("filters_applied", postgresql.JSONB(), nullable=True, comment="Filters applied"),
        sa.Column("result_count", sa.Integer(), nullable=False, comment="Number of results"),
        sa.Column("result_ids", postgresql.ARRAY(sa.String(36)), nullable=True, comment="IDs of returned results"),
        sa.Column("top_result_type", sa.String(50), nullable=True, comment="Type of top result"),
        sa.Column("search_duration_ms", sa.Integer(), nullable=True, comment="Search duration in ms"),
        sa.Column("clicked_result_id", postgresql.UUID(as_uuid=True), nullable=True, comment="Result clicked by user"),
        sa.Column("feedback_helpful", sa.Boolean(), nullable=True, comment="User feedback"),
        sa.Column("feedback_notes", sa.Text(), nullable=True, comment="Additional feedback"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kb_search_logs")),
    )

    # Create indexes for kb_search_logs
    op.create_index(op.f("ix_kb_search_logs_user_id"), "kb_search_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_kb_search_logs_session_id"), "kb_search_logs", ["session_id"], unique=False)
    op.create_index(op.f("ix_kb_search_logs_created_at"), "kb_search_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_kb_search_logs_search_type"), "kb_search_logs", ["search_type"], unique=False)
    op.create_index("ix_kb_search_logs_created_at_user", "kb_search_logs", ["created_at", "user_id"], unique=False)

    # Create GIN indexes for array columns to support efficient array searches
    op.execute("CREATE INDEX ix_actuarial_methods_tags ON actuarial_methods USING GIN (tags)")
    op.execute("CREATE INDEX ix_actuarial_methods_related_standards ON actuarial_methods USING GIN (related_standards)")
    op.execute("CREATE INDEX ix_templates_tags ON templates USING GIN (tags)")
    op.execute("CREATE INDEX ix_precedents_tags ON precedents USING GIN (tags)")
    op.execute("CREATE INDEX ix_precedents_methods_used ON precedents USING GIN (methods_used)")

    # Create full-text search indexes
    op.execute("""
        CREATE INDEX ix_actuarial_methods_fts ON actuarial_methods
        USING GIN (to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')))
    """)
    op.execute("""
        CREATE INDEX ix_templates_fts ON templates
        USING GIN (to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')))
    """)
    op.execute("""
        CREATE INDEX ix_precedents_fts ON precedents
        USING GIN (to_tsvector('english', title || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')))
    """)


def downgrade() -> None:
    """Drop knowledge base tables and types."""

    # Drop full-text search indexes
    op.execute("DROP INDEX IF EXISTS ix_precedents_fts")
    op.execute("DROP INDEX IF EXISTS ix_templates_fts")
    op.execute("DROP INDEX IF EXISTS ix_actuarial_methods_fts")

    # Drop GIN indexes
    op.execute("DROP INDEX IF EXISTS ix_precedents_methods_used")
    op.execute("DROP INDEX IF EXISTS ix_precedents_tags")
    op.execute("DROP INDEX IF EXISTS ix_templates_tags")
    op.execute("DROP INDEX IF EXISTS ix_actuarial_methods_related_standards")
    op.execute("DROP INDEX IF EXISTS ix_actuarial_methods_tags")

    # Drop tables
    op.drop_table("kb_search_logs")
    op.drop_table("precedents")
    op.drop_table("templates")
    op.drop_table("actuarial_methods")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS kb_status")
    op.execute("DROP TYPE IF EXISTS kb_type")
    op.execute("DROP TYPE IF EXISTS kb_category")

    # Note: We don't drop the vector extension as it might be used by other tables
