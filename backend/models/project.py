"""
Project models for organizing work within engagements.

A project represents a discrete unit of work within an engagement,
allowing for better organization of related tasks, workflows, and artefacts.
"""

from datetime import date
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, Enum as SQLEnum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, UUIDMixin


if TYPE_CHECKING:
    from models.engagement import Engagement


class ProjectStatus(str, Enum):
    """Status of a project."""

    DRAFT = "draft"
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class ProjectPriority(str, Enum):
    """Priority level for a project."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Project(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Project representing a discrete unit of work within an engagement.

    Projects provide additional organizational structure within engagements,
    allowing teams to group related work, track progress, and manage
    project-level settings and metadata.

    Attributes:
        engagement_id: Parent engagement this project belongs to
        name: Project name/title
        description: Detailed project description
        code: Short project code for reference (e.g., "PROJ-001")
        status: Current project status
        priority: Project priority level
        owner_id: User responsible for the project
        start_date: Planned or actual start date
        end_date: Planned or actual end date
        due_date: Project deadline
        estimated_hours: Estimated effort in hours
        actual_hours: Actual effort spent in hours
        progress_percent: Completion percentage (0-100)
        settings: Project-level configuration settings
        extra_metadata: Additional metadata (tags, custom fields, etc.)
    """

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_percent_range",
        ),
    )

    # Parent engagement reference
    engagement_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent engagement this project belongs to",
    )

    # Project identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Project name/title",
    )

    code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        unique=True,
        comment="Short project code for reference (e.g., PROJ-001)",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed project description",
    )

    # Status and priority
    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus, name="project_status", create_constraint=True),
        default=ProjectStatus.DRAFT,
        server_default=text("'draft'"),
        nullable=False,
        index=True,
    )

    priority: Mapped[ProjectPriority] = mapped_column(
        SQLEnum(ProjectPriority, name="project_priority", create_constraint=True),
        default=ProjectPriority.MEDIUM,
        server_default=text("'medium'"),
        nullable=False,
        index=True,
    )

    # Ownership and responsibility
    owner_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="User responsible for the project (Supabase auth.users)",
    )

    # Timeline
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Planned or actual start date",
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Planned or actual end date",
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Project deadline",
    )

    # Effort tracking
    estimated_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated effort in hours",
    )

    actual_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=0,
        comment="Actual effort spent in hours",
    )

    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Completion percentage (0-100)",
    )

    # Project-level settings and configuration
    settings: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Project-level configuration settings",
    )

    # Named extra_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",  # Keep DB column name as 'metadata' for consistency
        comment="Additional metadata: tags, custom fields, labels, etc.",
    )

    # Relationships
    # Note: Use lazy="raise" to prevent accidental N+1 queries.
    # Explicitly load relationships when needed using selectinload() or joinedload()
    engagement: Mapped["Engagement"] = relationship(
        "Engagement",
        back_populates="projects",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        status_value = self.status.value if self.status else None
        return (
            f"<Project(id={self.id}, code={self.code!r}, "
            f"name={self.name!r}, status={status_value})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if the project is in an active state."""
        return self.status == ProjectStatus.ACTIVE

    @property
    def is_editable(self) -> bool:
        """Check if the project can be modified."""
        if self.status is None:
            return True  # New projects without status are editable
        return self.status in (
            ProjectStatus.DRAFT,
            ProjectStatus.PLANNING,
            ProjectStatus.ACTIVE,
            ProjectStatus.ON_HOLD,
        )

    @property
    def is_overdue(self) -> bool:
        """Check if the project is past its due date.

        A project is considered overdue if:
        - It has a due date set
        - The due date has passed
        - The project is not in a terminal state (completed, archived, cancelled)
        """
        if self.due_date is None:
            return False
        if self.status is None:
            return date.today() > self.due_date
        if self.status in (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED, ProjectStatus.CANCELLED):
            return False
        return date.today() > self.due_date

    def activate(self) -> None:
        """Transition project to active status."""
        valid_statuses = (ProjectStatus.DRAFT, ProjectStatus.PLANNING, ProjectStatus.ON_HOLD)
        if self.status is not None and self.status not in valid_statuses:
            raise ValueError(f"Cannot activate project in {self.status.value} status")
        self.status = ProjectStatus.ACTIVE

    def complete(self) -> None:
        """Mark project as completed."""
        if self.status not in (ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD):
            status_desc = self.status.value if self.status else "unset"
            raise ValueError(f"Cannot complete project in {status_desc} status")
        self.status = ProjectStatus.COMPLETED
        self.progress_percent = 100

    def archive(self) -> None:
        """Archive a completed or cancelled project."""
        if self.status not in (ProjectStatus.COMPLETED, ProjectStatus.CANCELLED):
            status_desc = self.status.value if self.status else "unset"
            raise ValueError(f"Cannot archive project in {status_desc} status")
        self.status = ProjectStatus.ARCHIVED

    def put_on_hold(self) -> None:
        """Put an active project on hold."""
        if self.status != ProjectStatus.ACTIVE:
            status_desc = self.status.value if self.status else "unset"
            raise ValueError(f"Cannot put project on hold from {status_desc} status")
        self.status = ProjectStatus.ON_HOLD

    def cancel(self) -> None:
        """Cancel the project."""
        terminal_statuses = (ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED)
        if self.status is not None and self.status in terminal_statuses:
            raise ValueError(f"Cannot cancel project in {self.status.value} status")
        self.status = ProjectStatus.CANCELLED

    def update_progress(self, percent: int) -> None:
        """Update project progress percentage.

        Args:
            percent: Progress percentage (0-100)
        """
        if not 0 <= percent <= 100:
            raise ValueError("Progress must be between 0 and 100")
        self.progress_percent = percent
