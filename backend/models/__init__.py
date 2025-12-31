"""
SQLAlchemy ORM models for the AI Actuary application.

This module exports all database models for use throughout the application.
Models are organized by domain:

- base: Common mixins and base functionality
- session: User sessions and chat history
- audit: Audit trails and activity logging
- engagement: Client engagements and projects
- project: Projects within engagements
- workflow: Workflow runs and execution tracking
- artefact: Generated artefacts and file storage
- approval: Professional approval workflows
- backup: Backup and recovery tracking
- cli_task: CLI task execution and tracking (Codex CLI integration)
- knowledge_base: Actuarial methods, templates, and precedents with vector search
"""

from models.base import AuditMixin, SoftDeleteMixin, TimestampMixin, TraceableMixin, UUIDMixin
from models.session import ChatMessage, MessageRole, Session
from models.audit import AuditAction, AuditLog, AuditSeverity
from models.engagement import Engagement, EngagementStatus, EngagementType
from models.project import Project, ProjectPriority, ProjectStatus
from models.workflow import WorkflowRun, WorkflowStatus, WorkflowType
from models.artefact import Artefact, ArtefactStatus, ArtefactType
from models.approval import Approval, ApprovalStatus, ApprovalType
from models.backup import Backup, BackupStatus, BackupType, Recovery, RecoveryStatus
from models.trace import TraceSpan
from models.cli_task import CLITask, CLITaskPriority, CLITaskStatus, CLITaskType
from models.knowledge_base import (
    ActuarialMethod,
    KnowledgeBaseCategory,
    KnowledgeBaseSearchLog,
    KnowledgeBaseStatus,
    KnowledgeBaseType,
    Precedent,
    Template,
)
from models.orchestration import (
    AgentHandoff,
    HandoffReasonDB,
    OrchestrationMetrics,
    RoutingDecisionLog,
    RoutingOutcome,
)
from models.metrics import (
    AgentMetric,
    AggregatedMetrics,
    MetricType,
)

__all__ = [
    # Base mixins
    "UUIDMixin",
    "TimestampMixin",
    "AuditMixin",
    "SoftDeleteMixin",
    "TraceableMixin",
    # Session models
    "Session",
    "ChatMessage",
    "MessageRole",
    # Audit models
    "AuditLog",
    "AuditAction",
    "AuditSeverity",
    # Engagement models
    "Engagement",
    "EngagementStatus",
    "EngagementType",
    # Project models
    "Project",
    "ProjectPriority",
    "ProjectStatus",
    # Workflow models
    "WorkflowRun",
    "WorkflowStatus",
    "WorkflowType",
    # Artefact models
    "Artefact",
    "ArtefactType",
    "ArtefactStatus",
    # Approval models
    "Approval",
    "ApprovalStatus",
    "ApprovalType",
    # Backup models
    "Backup",
    "BackupStatus",
    "BackupType",
    "Recovery",
    "RecoveryStatus",
    # Trace models
    "TraceSpan",
    # CLI Task models (Codex CLI integration)
    "CLITask",
    "CLITaskStatus",
    "CLITaskType",
    "CLITaskPriority",
    # Knowledge Base models
    "ActuarialMethod",
    "Template",
    "Precedent",
    "KnowledgeBaseCategory",
    "KnowledgeBaseType",
    "KnowledgeBaseStatus",
    "KnowledgeBaseSearchLog",
    # Orchestration models
    "AgentHandoff",
    "HandoffReasonDB",
    "RoutingDecisionLog",
    "RoutingOutcome",
    "OrchestrationMetrics",
    # Agent Metrics models
    "AgentMetric",
    "AggregatedMetrics",
    "MetricType",
]
