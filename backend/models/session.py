"""
Session and chat message models for conversation persistence.

Stores user sessions and chat history for the AI Actuary assistant.
Enables conversation continuity and historical analysis.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from models.base import AuditMixin, SoftDeleteMixin, TraceableMixin, UUIDMixin

if TYPE_CHECKING:
    from models.engagement import Engagement


class MessageRole(str, Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Session(Base, UUIDMixin, AuditMixin, SoftDeleteMixin, TraceableMixin):
    """
    User session representing a conversation with the AI Actuary.

    A session contains multiple chat messages and may be associated with
    an engagement for context. Sessions are scoped to authenticated users.
    """

    __tablename__ = "sessions"

    # User association (references Supabase auth.users)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to Supabase auth.users.id",
    )

    # Optional engagement association
    engagement_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Session metadata
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User-defined or auto-generated session title",
    )

    # Session context and configuration
    context: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Session context including active agent, preferences",
    )

    # Session timing
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    # Note: Use lazy="raise" to prevent accidental N+1 queries.
    # Explicitly load relationships when needed using selectinload() or joinedload()
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
        lazy="raise",  # Require explicit loading to prevent N+1 queries
    )

    engagement: Mapped["Engagement | None"] = relationship(
        "Engagement",
        back_populates="sessions",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, title={self.title!r})>"

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity_at = datetime.now(timezone.utc)


class ChatMessage(Base, UUIDMixin, TraceableMixin):
    """
    Individual chat message within a session.

    Stores the content, role, and metadata for each message in the conversation.
    Supports tool calls and structured data in the metadata field.
    """

    __tablename__ = "chat_messages"

    # Session association
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole, name="message_role", create_constraint=True),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Tool call information (for assistant tool calls and tool responses)
    tool_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of the tool called (for role=tool messages)",
    )

    tool_call_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Tool call ID linking request and response",
    )

    # Message metadata (model info, tokens, etc.)
    # Named message_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    message_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        name="metadata",  # Keep DB column name as 'metadata' for backward compatibility
        comment="Additional metadata: model, tokens, latency, etc.",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Parent message for threading (optional)
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="messages",
        lazy="raise",  # Require explicit loading
    )

    parent: Mapped["ChatMessage | None"] = relationship(
        "ChatMessage",
        remote_side="ChatMessage.id",
        lazy="raise",  # Require explicit loading
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, role={self.role.value}, content={content_preview!r})>"
