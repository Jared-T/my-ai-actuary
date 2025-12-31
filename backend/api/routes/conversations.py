"""
Conversation history API routes.

Provides endpoints for:
- Fetching conversation history for a session with pagination
- Filtering messages by role, date, and text search
- Optional summary generation
- Conversation statistics
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import CurrentUser
from core.database import get_db
from core.logging import get_logger
from models.session import MessageRole
from services.conversation_service import ConversationService

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["Conversations"])


# Request/Response Models
class ChatMessageResponse(BaseModel):
    """Response model for a single chat message."""

    id: str = Field(description="Message ID")
    role: str = Field(description="Message role (user, assistant, system, tool)")
    content: str = Field(description="Message content")
    tool_name: Optional[str] = Field(default=None, description="Tool name if role is tool")
    tool_call_id: Optional[str] = Field(default=None, description="Tool call ID")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Message metadata")
    created_at: str = Field(description="Message creation timestamp")
    parent_id: Optional[str] = Field(default=None, description="Parent message ID for threading")


class ConversationSummary(BaseModel):
    """Model for a conversation summary."""

    summary: str = Field(description="Text summary of the conversation")
    key_points: list[str] = Field(description="Key points extracted from the conversation")
    generated_at: str = Field(description="Timestamp when the summary was generated")


class PaginationInfo(BaseModel):
    """Pagination metadata."""

    total: int = Field(description="Total number of messages matching filters")
    limit: int = Field(description="Maximum messages per page")
    offset: int = Field(description="Current offset")
    has_more: bool = Field(description="Whether there are more messages")


class SessionInfo(BaseModel):
    """Basic session information."""

    id: str = Field(description="Session ID")
    title: Optional[str] = Field(default=None, description="Session title")
    created_at: str = Field(description="Session creation timestamp")
    last_activity_at: str = Field(description="Last activity timestamp")


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history endpoint."""

    session: SessionInfo = Field(description="Session information")
    messages: list[ChatMessageResponse] = Field(description="List of chat messages")
    pagination: PaginationInfo = Field(description="Pagination metadata")
    summary: Optional[ConversationSummary] = Field(
        default=None, description="Optional conversation summary"
    )


class ConversationStatsResponse(BaseModel):
    """Response model for conversation statistics."""

    session_id: str = Field(description="Session ID")
    total_messages: int = Field(description="Total number of messages")
    messages_by_role: dict[str, int] = Field(description="Message count by role")
    first_message_at: Optional[str] = Field(
        default=None, description="Timestamp of first message"
    )
    last_message_at: Optional[str] = Field(
        default=None, description="Timestamp of last message"
    )


# Endpoints
@router.get(
    "/{session_id}/messages",
    response_model=ConversationHistoryResponse,
    summary="Get conversation history",
    description="Retrieve conversation history for a session with pagination, filtering, and optional summary.",
)
async def get_conversation_history(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    role: Optional[MessageRole] = Query(
        default=None, description="Filter by message role"
    ),
    from_date: Optional[datetime] = Query(
        default=None, description="Filter messages from this date"
    ),
    to_date: Optional[datetime] = Query(
        default=None, description="Filter messages until this date"
    ),
    search: Optional[str] = Query(
        default=None, description="Search text within message content"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum messages to return"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
    include_summary: bool = Query(
        default=False, description="Include AI-generated conversation summary"
    ),
    summary_max_tokens: int = Query(
        default=300, ge=50, le=1000, description="Maximum tokens for summary"
    ),
) -> ConversationHistoryResponse:
    """
    Get conversation history for a session.

    Retrieves chat messages with support for:
    - Pagination using limit/offset
    - Filtering by role, date range, and text search
    - Optional AI-generated summary of the conversation

    The endpoint requires authentication and verifies the user owns the session.
    """
    logger.info(
        "Fetching conversation history",
        session_id=str(session_id),
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
        include_summary=include_summary,
    )

    service = ConversationService(db)

    # Verify session exists and user owns it
    session = await service.get_session(session_id, current_user.id)
    if not session:
        logger.warning(
            "Session not found or access denied",
            session_id=str(session_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you don't have access to it",
        )

    # Get messages with filters
    messages = await service.get_messages(
        session_id=session_id,
        role=role,
        from_date=from_date,
        to_date=to_date,
        search_text=search,
        limit=limit,
        offset=offset,
    )

    # Get total count for pagination
    total = await service.count_messages(
        session_id=session_id,
        role=role,
        from_date=from_date,
        to_date=to_date,
        search_text=search,
    )

    # Generate summary if requested
    summary = None
    if include_summary and messages:
        summary_data = await service.generate_summary(
            messages=messages,
            max_tokens=summary_max_tokens,
        )
        summary = ConversationSummary(**summary_data)

    # Build response
    return ConversationHistoryResponse(
        session=SessionInfo(
            id=str(session.id),
            title=session.title,
            created_at=session.created_at.isoformat(),
            last_activity_at=session.last_activity_at.isoformat(),
        ),
        messages=[
            ChatMessageResponse(
                id=str(msg.id),
                role=msg.role.value,
                content=msg.content,
                tool_name=msg.tool_name,
                tool_call_id=msg.tool_call_id,
                metadata=msg.message_metadata,
                created_at=msg.created_at.isoformat(),
                parent_id=str(msg.parent_id) if msg.parent_id else None,
            )
            for msg in messages
        ],
        pagination=PaginationInfo(
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(messages)) < total,
        ),
        summary=summary,
    )


@router.get(
    "/{session_id}/stats",
    response_model=ConversationStatsResponse,
    summary="Get conversation statistics",
    description="Get statistics about a conversation including message counts by role.",
)
async def get_conversation_stats(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ConversationStatsResponse:
    """
    Get statistics for a conversation.

    Returns message counts, role breakdown, and timestamps.
    Requires authentication and verifies session ownership.
    """
    logger.info(
        "Fetching conversation stats",
        session_id=str(session_id),
        user_id=str(current_user.id),
    )

    service = ConversationService(db)

    # Verify session exists and user owns it
    session = await service.get_session(session_id, current_user.id)
    if not session:
        logger.warning(
            "Session not found or access denied",
            session_id=str(session_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you don't have access to it",
        )

    stats = await service.get_conversation_stats(session_id)

    return ConversationStatsResponse(
        session_id=str(session_id),
        **stats,
    )


@router.get(
    "/{session_id}/summary",
    response_model=ConversationSummary,
    summary="Generate conversation summary",
    description="Generate an AI-powered summary of the conversation.",
)
async def generate_conversation_summary(
    session_id: UUID,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    max_tokens: int = Query(
        default=300, ge=50, le=1000, description="Maximum tokens for summary"
    ),
    limit: int = Query(
        default=100, ge=10, le=500, description="Number of recent messages to summarize"
    ),
) -> ConversationSummary:
    """
    Generate a summary of the conversation.

    Uses AI to create a concise summary and extract key points.
    Requires authentication and verifies session ownership.
    """
    logger.info(
        "Generating conversation summary",
        session_id=str(session_id),
        user_id=str(current_user.id),
        max_tokens=max_tokens,
        message_limit=limit,
    )

    service = ConversationService(db)

    # Verify session exists and user owns it
    session = await service.get_session(session_id, current_user.id)
    if not session:
        logger.warning(
            "Session not found or access denied",
            session_id=str(session_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you don't have access to it",
        )

    # Get messages for summarization
    messages = await service.get_messages(
        session_id=session_id,
        limit=limit,
        offset=0,
    )

    if not messages:
        logger.info(
            "No messages to summarize",
            session_id=str(session_id),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages in this session to summarize",
        )

    summary_data = await service.generate_summary(
        messages=messages,
        max_tokens=max_tokens,
    )

    logger.info(
        "Generated conversation summary successfully",
        session_id=str(session_id),
        key_points_count=len(summary_data.get("key_points", [])),
    )

    return ConversationSummary(**summary_data)
