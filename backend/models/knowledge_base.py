"""
Knowledge base models for actuarial methods, templates, and precedents.

Provides vector-enabled storage for semantic search capabilities using pgvector.
Supports three main content types:
- Methods: Actuarial methods and techniques (Chain ladder, IBNR, BBA, PAA, etc.)
- Templates: Document templates and report structures
- Precedents: Historical cases and reference implementations
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, TraceableMixin, UUIDMixin

# Note: Vector type will be imported conditionally and handled in migration


class KnowledgeBaseCategory(str, Enum):
    """Categories for knowledge base entries."""

    # Actuarial Methods
    RESERVING = "reserving"
    IFRS17 = "ifrs17"
    ALM = "alm"
    REINSURANCE = "reinsurance"
    PRICING = "pricing"
    VALUATION = "valuation"
    DATA_QUALITY = "data_quality"
    REPORTING = "reporting"

    # General
    REGULATORY = "regulatory"
    METHODOLOGY = "methodology"
    BEST_PRACTICE = "best_practice"
    OTHER = "other"


class KnowledgeBaseType(str, Enum):
    """Types of knowledge base entries."""

    METHOD = "method"  # Actuarial methods and techniques
    TEMPLATE = "template"  # Document templates and structures
    PRECEDENT = "precedent"  # Historical cases and examples
    REFERENCE = "reference"  # Reference materials and documentation
    GUIDANCE = "guidance"  # Regulatory guidance and standards


class KnowledgeBaseStatus(str, Enum):
    """Status of knowledge base entries."""

    DRAFT = "draft"  # Being prepared, not searchable
    ACTIVE = "active"  # Available for search and retrieval
    UNDER_REVIEW = "under_review"  # Being reviewed for updates
    DEPRECATED = "deprecated"  # Superseded but still accessible
    ARCHIVED = "archived"  # No longer in use


class ActuarialMethod(Base, UUIDMixin, AuditMixin, SoftDeleteMixin, TraceableMixin):
    """
    Actuarial methods and techniques library.

    Stores detailed information about actuarial methods including:
    - Method descriptions and use cases
    - Mathematical formulations
    - Implementation guidance
    - Related standards and regulations
    - Vector embeddings for semantic search
    """

    __tablename__ = "actuarial_methods"

    # Method identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Method name (e.g., 'Chain Ladder', 'Bornhuetter-Ferguson')",
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Short code for the method (e.g., 'CHAIN_LADDER', 'BF')",
    )

    category: Mapped[KnowledgeBaseCategory] = mapped_column(
        SQLEnum(KnowledgeBaseCategory, name="kb_category", create_constraint=True),
        nullable=False,
        index=True,
        comment="Primary category for the method",
    )

    # Content
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief summary of the method (1-2 sentences)",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of the method",
    )

    use_cases: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Typical use cases and scenarios",
    )

    mathematical_formulation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mathematical formulas and notation (LaTeX supported)",
    )

    implementation_guidance: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Step-by-step implementation guidance",
    )

    limitations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Known limitations and constraints",
    )

    # Metadata
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        SQLEnum(KnowledgeBaseStatus, name="kb_status", create_constraint=True),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
        comment="Tags for categorization and filtering",
    )

    related_standards: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="Related regulatory standards (e.g., 'IFRS 17', 'SAM')",
    )

    version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
        comment="Version of the method documentation",
    )

    # Search and ranking
    search_priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Priority for search results (higher = more prominent)",
    )

    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Number of times this method has been referenced",
    )

    # Vector embedding for semantic search
    # Stored as a TEXT column containing JSON array - will be converted to vector in queries
    # This approach allows flexibility without requiring pgvector extension at model level
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Vector embedding as JSON array for semantic search",
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Model used to generate embedding (e.g., 'text-embedding-3-small')",
    )

    embedding_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last embedding update",
    )

    # Extended metadata
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",
        comment="Additional metadata and properties",
    )

    def __repr__(self) -> str:
        return f"<ActuarialMethod(code={self.code!r}, name={self.name!r})>"


class Template(Base, UUIDMixin, AuditMixin, SoftDeleteMixin, TraceableMixin):
    """
    Document templates for actuarial reports and deliverables.

    Stores template information including:
    - Template structure and sections
    - Required data inputs
    - Output format specifications
    - Vector embeddings for semantic search
    """

    __tablename__ = "templates"

    # Template identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Template name",
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Short code for the template",
    )

    template_type: Mapped[KnowledgeBaseType] = mapped_column(
        SQLEnum(KnowledgeBaseType, name="kb_type", create_constraint=True),
        default=KnowledgeBaseType.TEMPLATE,
        nullable=False,
        index=True,
    )

    category: Mapped[KnowledgeBaseCategory] = mapped_column(
        SQLEnum(KnowledgeBaseCategory, name="kb_category", create_constraint=False),
        nullable=False,
        index=True,
    )

    # Content
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief description of the template",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description and usage instructions",
    )

    # Template structure
    structure: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Template structure definition (sections, fields, etc.)",
    )

    required_inputs: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Required data inputs for the template",
    )

    output_format: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Output format (e.g., 'word', 'pdf', 'excel', 'markdown')",
    )

    # Template content/body
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Template content or reference to storage location",
    )

    storage_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Path to template file in storage",
    )

    # Metadata
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        SQLEnum(KnowledgeBaseStatus, name="kb_status", create_constraint=False),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
        comment="Tags for categorization",
    )

    version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
    )

    # Search and ranking
    search_priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    # Vector embedding
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Vector embedding as JSON array for semantic search",
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    embedding_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Extended metadata
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",
    )

    def __repr__(self) -> str:
        return f"<Template(code={self.code!r}, name={self.name!r})>"


class Precedent(Base, UUIDMixin, AuditMixin, SoftDeleteMixin, TraceableMixin):
    """
    Historical cases and precedent examples.

    Stores information about past actuarial work including:
    - Case descriptions and contexts
    - Methods and approaches used
    - Outcomes and lessons learned
    - Vector embeddings for finding similar cases
    """

    __tablename__ = "precedents"

    # Precedent identification
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Precedent title",
    )

    reference_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Unique reference code for the precedent",
    )

    category: Mapped[KnowledgeBaseCategory] = mapped_column(
        SQLEnum(KnowledgeBaseCategory, name="kb_category", create_constraint=False),
        nullable=False,
        index=True,
    )

    # Content
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Brief summary of the case",
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed case description",
    )

    context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Business context and background",
    )

    # Case details
    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Industry sector (e.g., 'Life Insurance', 'P&C', 'Health')",
    )

    jurisdiction: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Regulatory jurisdiction",
    )

    reporting_period: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Reporting period or date range",
    )

    # Methods and outcomes
    methods_used: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="Actuarial methods applied",
    )

    approach_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the approach taken",
    )

    outcome: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Results and outcomes",
    )

    lessons_learned: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Key lessons and takeaways",
    )

    # Related artifacts (references to documents, not actual files)
    related_artefacts: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="References to related artefacts and documents",
    )

    # Metadata
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        SQLEnum(KnowledgeBaseStatus, name="kb_status", create_constraint=False),
        default=KnowledgeBaseStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)),
        nullable=True,
    )

    confidentiality_level: Mapped[str] = mapped_column(
        String(50),
        default="internal",
        nullable=False,
        comment="Confidentiality level (public, internal, restricted, confidential)",
    )

    # Anonymization flag - indicates if client data has been anonymized
    is_anonymized: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the case has been anonymized",
    )

    # Search and ranking
    search_priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    relevance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Pre-computed relevance score for general searches",
    )

    # Vector embedding
    embedding: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Vector embedding as JSON array for semantic search",
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    embedding_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Extended metadata
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",
    )

    def __repr__(self) -> str:
        return f"<Precedent(reference_code={self.reference_code!r}, title={self.title!r})>"


class KnowledgeBaseSearchLog(Base, UUIDMixin):
    """
    Log of knowledge base searches for analytics and improvement.

    Tracks search queries, results, and user feedback to:
    - Improve search relevance
    - Identify knowledge gaps
    - Track usage patterns
    """

    __tablename__ = "kb_search_logs"

    # Search context
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User who performed the search",
    )

    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Session context for the search",
    )

    # Search parameters
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Search query text",
    )

    search_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of search (semantic, keyword, hybrid)",
    )

    filters_applied: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Filters applied to the search",
    )

    # Results
    result_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of results returned",
    )

    result_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(36)),
        nullable=True,
        comment="IDs of returned results",
    )

    top_result_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of the top result (method, template, precedent)",
    )

    # Performance metrics
    search_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Search duration in milliseconds",
    )

    # User feedback
    clicked_result_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="ID of result the user clicked on",
    )

    feedback_helpful: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="User feedback on search helpfulness",
    )

    feedback_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional user feedback",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseSearchLog(query={self.query[:50]!r}...)>"


# Indexes for efficient searching
# Note: These will be created in the migration with proper vector index support
__table_args__ = (
    Index("ix_actuarial_methods_category_status", "category", "status"),
    Index("ix_templates_category_status", "category", "status"),
    Index("ix_precedents_category_status", "category", "status"),
    Index("ix_kb_search_logs_created_at_user", "created_at", "user_id"),
)
