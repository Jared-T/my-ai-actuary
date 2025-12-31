"""
Conversation history retrieval service.

Provides:
- Fetching conversation history for a session with pagination
- Filtering messages by role, date range, and other criteria
- Optional summary generation using LLM
- Message count for pagination metadata
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from models.session import ChatMessage, MessageRole, Session

logger = get_logger(__name__)


def _escape_like_pattern(search_text: str) -> str:
    """
    Escape special characters in LIKE pattern to prevent SQL injection.

    Args:
        search_text: The raw search text from user input

    Returns:
        Escaped search text safe for use in LIKE patterns
    """
    # Escape special LIKE characters: %, _, and backslash
    return (
        search_text
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


class ConversationService:
    """
    Service for retrieving and managing conversation history.

    Provides methods for:
    - Querying messages with pagination and filtering
    - Generating conversation summaries
    - Computing message counts
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the conversation service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> Session | None:
        """
        Get a session by ID, verifying ownership.

        Args:
            session_id: Session ID
            user_id: User ID for ownership verification

        Returns:
            Session if found and owned by user, None otherwise
        """
        stmt = select(Session).where(
            and_(
                Session.id == session_id,
                Session.user_id == user_id,
                Session.is_deleted == False,  # noqa: E712
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _build_message_filters(
        self,
        session_id: UUID,
        role: MessageRole | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search_text: str | None = None,
    ) -> list:
        """
        Build SQLAlchemy filter conditions for message queries.

        Args:
            session_id: Session ID to filter by
            role: Optional role filter
            from_date: Optional start date filter
            to_date: Optional end date filter
            search_text: Optional text search filter

        Returns:
            List of SQLAlchemy filter conditions
        """
        filters = [ChatMessage.session_id == session_id]

        if role:
            filters.append(ChatMessage.role == role)
        if from_date:
            filters.append(ChatMessage.created_at >= from_date)
        if to_date:
            filters.append(ChatMessage.created_at <= to_date)
        if search_text:
            # Escape special LIKE characters and use case-insensitive search
            escaped_text = _escape_like_pattern(search_text)
            filters.append(ChatMessage.content.ilike(f"%{escaped_text}%"))

        return filters

    async def get_messages(
        self,
        session_id: UUID,
        role: MessageRole | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """
        Query chat messages with filters and pagination.

        Args:
            session_id: Session ID to retrieve messages for
            role: Filter by message role (user, assistant, system, tool)
            from_date: Filter messages created after this date
            to_date: Filter messages created before this date
            search_text: Search for text within message content
            limit: Maximum results (default 50)
            offset: Result offset for pagination

        Returns:
            List of matching chat messages
        """
        filters = self._build_message_filters(
            session_id=session_id,
            role=role,
            from_date=from_date,
            to_date=to_date,
            search_text=search_text,
        )

        stmt = (
            select(ChatMessage)
            .where(and_(*filters))
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())

        logger.debug(
            "Retrieved conversation messages",
            session_id=str(session_id),
            message_count=len(messages),
            limit=limit,
            offset=offset,
        )

        return messages

    async def count_messages(
        self,
        session_id: UUID,
        role: MessageRole | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search_text: str | None = None,
    ) -> int:
        """
        Count total messages matching filters.

        Args:
            session_id: Session ID
            role: Filter by message role
            from_date: Filter messages created after this date
            to_date: Filter messages created before this date
            search_text: Search text filter

        Returns:
            Total count of matching messages
        """
        filters = self._build_message_filters(
            session_id=session_id,
            role=role,
            from_date=from_date,
            to_date=to_date,
            search_text=search_text,
        )

        stmt = select(func.count(ChatMessage.id)).where(and_(*filters))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def generate_summary(
        self,
        messages: list[ChatMessage],
        max_tokens: int = 300,
    ) -> dict[str, Any]:
        """
        Generate a summary of the conversation using LLM.

        Args:
            messages: List of chat messages to summarize
            max_tokens: Maximum tokens for the summary

        Returns:
            Dictionary with summary text and key points
        """
        if not messages:
            return {
                "summary": "No messages to summarize.",
                "key_points": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Build conversation text for summarization
        conversation_text = "\n".join(
            f"{msg.role.value.upper()}: {msg.content}" for msg in messages
        )

        # Truncate if too long (roughly 4 chars per token)
        max_chars = max_tokens * 16  # Allow more context for summarization
        if len(conversation_text) > max_chars:
            conversation_text = conversation_text[:max_chars] + "\n[Conversation truncated...]"

        try:
            # Use OpenAI for summary generation
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant that summarizes conversations. "
                            "Provide a concise summary of the conversation and extract "
                            "3-5 key points. Format your response as JSON with 'summary' "
                            "(string) and 'key_points' (array of strings) fields."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize this conversation:\n\n{conversation_text}",
                    },
                ],
                max_tokens=max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content or "{}"
            result = json.loads(result_text)

            logger.debug(
                "Generated conversation summary",
                message_count=len(messages),
                summary_length=len(result.get("summary", "")),
            )

            return {
                "summary": result.get("summary", "Unable to generate summary."),
                "key_points": result.get("key_points", []),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(
                "Failed to generate conversation summary",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "summary": "Unable to generate summary due to an error.",
                "key_points": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }

    async def get_conversation_stats(
        self,
        session_id: UUID,
    ) -> dict[str, Any]:
        """
        Get statistics about a conversation.

        Uses a single optimized query with GROUP BY to avoid N+1 query problem.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with conversation statistics
        """
        # Single query to get all stats: total, per-role counts, and timestamps
        stats_stmt = select(
            func.count(ChatMessage.id).label("total"),
            func.min(ChatMessage.created_at).label("first_message_at"),
            func.max(ChatMessage.created_at).label("last_message_at"),
        ).where(ChatMessage.session_id == session_id)

        stats_result = await self.db.execute(stats_stmt)
        stats_row = stats_result.one()

        total_count = stats_row.total or 0
        first_timestamp = stats_row.first_message_at
        last_timestamp = stats_row.last_message_at

        # Single query to get counts by role using GROUP BY
        role_stmt = (
            select(
                ChatMessage.role,
                func.count(ChatMessage.id).label("count"),
            )
            .where(ChatMessage.session_id == session_id)
            .group_by(ChatMessage.role)
        )

        role_result = await self.db.execute(role_stmt)
        role_counts = {row.role.value: row.count for row in role_result.all()}

        logger.debug(
            "Retrieved conversation stats",
            session_id=str(session_id),
            total_messages=total_count,
            role_count=len(role_counts),
        )

        return {
            "total_messages": total_count,
            "messages_by_role": role_counts,
            "first_message_at": first_timestamp.isoformat() if first_timestamp else None,
            "last_message_at": last_timestamp.isoformat() if last_timestamp else None,
        }


async def get_conversation_service(db: AsyncSession) -> ConversationService:
    """
    FastAPI dependency for getting a ConversationService instance.

    Args:
        db: Database session

    Returns:
        Configured ConversationService instance
    """
    return ConversationService(db)
