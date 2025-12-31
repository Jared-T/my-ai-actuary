"""
Agent service for lifecycle management.

Provides high-level operations for creating, running, and managing agents
with proper session persistence and error handling.
"""

import os
import time
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_definitions.base import AgentRegistry, BaseAgent, GenericAgent
from agent_definitions.config import AgentType, get_agent_config, get_openai_api_key
from core.exceptions import AgentExecutionError, NotFoundError, ValidationError
from core.logging import get_logger
from models.session import ChatMessage, MessageRole, Session
from services.metrics_service import get_metrics_collector
from tools import BASE_TOOLS

logger = get_logger(__name__)

# Constants
DEFAULT_MESSAGE_LIMIT: Final[int] = 50


class AgentService:
    """
    Service for managing agent lifecycle and execution.

    Handles agent creation, session management, message persistence,
    and coordinated execution with proper error handling.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the agent service.

        Args:
            db: Database session for persistence operations
        """
        self.db = db
        self._ensure_api_key_set()

    def _ensure_api_key_set(self) -> None:
        """Ensure the OpenAI API key is set in the environment."""
        try:
            api_key = get_openai_api_key()
            # The agents SDK reads from OPENAI_API_KEY env var
            if not os.environ.get("OPENAI_API_KEY"):
                os.environ["OPENAI_API_KEY"] = api_key
        except ValueError:
            logger.warning("OpenAI API key not configured - agents will fail to run")

    async def get_or_create_session(
        self,
        user_id: UUID,
        session_id: UUID | None = None,
        engagement_id: UUID | None = None,
        title: str | None = None,
    ) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            user_id: The user's ID
            session_id: Optional existing session ID
            engagement_id: Optional engagement to associate with
            title: Optional session title

        Returns:
            Session instance
        """
        if session_id:
            stmt = select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
                Session.is_deleted == False,
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if session:
                session.update_activity()
                return session

        # Create new session
        session = Session(
            user_id=user_id,
            engagement_id=engagement_id,
            title=title or "New Conversation",
            context={
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(session)
        await self.db.flush()

        logger.info(
            "Created new session",
            session_id=str(session.id),
            user_id=str(user_id),
        )
        return session

    async def get_session_messages(
        self,
        session_id: UUID,
        limit: int = DEFAULT_MESSAGE_LIMIT,
    ) -> list[ChatMessage]:
        """
        Get messages for a session.

        Args:
            session_id: The session ID
            limit: Maximum number of messages to return

        Returns:
            List of chat messages ordered by creation time
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Return in chronological order
        return messages

    async def add_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> ChatMessage:
        """
        Add a message to a session.

        Args:
            session_id: The session ID
            role: Message role (user, assistant, system, tool)
            content: Message content
            tool_name: Optional tool name for tool messages
            tool_call_id: Optional tool call ID
            metadata: Optional additional metadata
            trace_id: Optional trace ID for correlation

        Returns:
            Created ChatMessage instance
        """
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            message_metadata=metadata,
            trace_id=trace_id,
        )
        self.db.add(message)
        await self.db.flush()

        logger.debug(
            "Added message",
            session_id=str(session_id),
            role=role.value,
            content_length=len(content),
        )
        return message

    def get_agent(
        self,
        agent_type: AgentType,
        tools: list[Any] | None = None,
    ) -> BaseAgent:
        """
        Get or create an agent of the specified type.

        Args:
            agent_type: The type of agent to get
            tools: Optional additional tools for the agent

        Returns:
            Agent instance
        """
        # Check if agent is already registered
        agent = AgentRegistry.get(agent_type)
        if agent:
            return agent

        # Create new agent with default config and tools
        all_tools = list(BASE_TOOLS)
        if tools:
            all_tools.extend(tools)

        agent = GenericAgent(
            agent_type=agent_type,
            tools=all_tools,
        )
        AgentRegistry.register(agent)
        return agent

    async def run_agent(
        self,
        user_id: UUID,
        message: str,
        agent_type: AgentType = AgentType.GENERAL,
        session_id: UUID | None = None,
        engagement_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run an agent with a user message.

        This is the main entry point for agent execution. It:
        1. Gets or creates a session
        2. Persists the user message
        3. Runs the agent
        4. Persists the assistant response
        5. Records performance metrics
        6. Returns the result

        Args:
            user_id: The user's ID
            message: The user's message
            agent_type: Type of agent to use
            session_id: Optional existing session ID
            engagement_id: Optional engagement ID
            context: Optional additional context

        Returns:
            Dictionary with response and session information
        """
        # Validate input
        if not message or not message.strip():
            raise ValidationError("Message cannot be empty")

        trace_id = str(uuid4())
        metrics_collector = get_metrics_collector()

        # Get or create session
        session = await self.get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            engagement_id=engagement_id,
        )

        # Update session context
        session.context = session.context or {}
        session.context["active_agent"] = agent_type.value
        session.context["last_trace_id"] = trace_id

        # Add user message
        await self.add_message(
            session_id=session.id,
            role=MessageRole.USER,
            content=message,
            trace_id=trace_id,
        )

        # Get agent
        agent = self.get_agent(agent_type)
        model = agent.config.model_settings.model

        # Track execution timing
        start_time = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        try:
            # Run agent
            result = await agent.run(
                input_text=message,
                context=context,
                trace_id=trace_id,
            )

            # Calculate timing
            end_time = datetime.now(timezone.utc)
            duration_ms = (time.perf_counter() - start_perf) * 1000

            # Extract response text
            response_text = result.final_output if hasattr(result, 'final_output') else str(result)

            # Extract token usage from result if available
            input_tokens = None
            output_tokens = None
            if hasattr(result, 'usage'):
                usage = result.usage
                if hasattr(usage, 'input_tokens'):
                    input_tokens = usage.input_tokens
                if hasattr(usage, 'output_tokens'):
                    output_tokens = usage.output_tokens
            elif hasattr(result, 'raw_responses') and result.raw_responses:
                # Try to extract from raw responses
                for raw in result.raw_responses:
                    if hasattr(raw, 'usage'):
                        usage = raw.usage
                        input_tokens = (input_tokens or 0) + getattr(usage, 'input_tokens', 0)
                        output_tokens = (output_tokens or 0) + getattr(usage, 'output_tokens', 0)

            # Record success metrics
            await metrics_collector.record_metric(
                db=self.db,
                agent_type=agent_type.value,
                model=model,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=True,
                input_length=len(message),
                output_length=len(response_text),
                trace_id=trace_id,
                session_id=session.id,
                user_id=user_id,
                agent_name=agent.name,
                metadata={
                    "has_tool_calls": hasattr(result, 'new_items') and len(getattr(result, 'new_items', [])) > 0,
                },
            )

            # Add assistant message with metrics
            await self.add_message(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                metadata={
                    "agent_type": agent_type.value,
                    "model": model,
                    "duration_ms": round(duration_ms, 2),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
                trace_id=trace_id,
            )

            logger.info(
                "Agent run completed",
                session_id=str(session.id),
                agent_type=agent_type.value,
                trace_id=trace_id,
                duration_ms=round(duration_ms, 2),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            return {
                "session_id": str(session.id),
                "trace_id": trace_id,
                "agent_type": agent_type.value,
                "response": response_text,
                "metadata": {
                    "model": model,
                    "duration_ms": round(duration_ms, 2),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            }

        except Exception as exc:
            # Calculate timing for failed execution
            end_time = datetime.now(timezone.utc)
            duration_ms = (time.perf_counter() - start_perf) * 1000

            # Record failure metrics
            error_type = type(exc).__name__
            error_message = str(exc)[:1000]  # Truncate long messages

            await metrics_collector.record_metric(
                db=self.db,
                agent_type=agent_type.value,
                model=model,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                success=False,
                error_type=error_type,
                error_message=error_message,
                input_length=len(message),
                trace_id=trace_id,
                session_id=session.id,
                user_id=user_id,
                agent_name=agent.name,
            )

            logger.error(
                "Agent execution failed",
                session_id=str(session.id),
                agent_type=agent_type.value,
                error=str(exc),
                error_type=error_type,
                trace_id=trace_id,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )

            # Add error message to session
            await self.add_message(
                session_id=session.id,
                role=MessageRole.SYSTEM,
                content=f"Agent execution failed: {str(exc)}",
                metadata={
                    "error": True,
                    "error_type": error_type,
                    "duration_ms": round(duration_ms, 2),
                },
                trace_id=trace_id,
            )

            raise AgentExecutionError(
                agent_name=agent.name,
                message=str(exc),
                details={
                    "session_id": str(session.id),
                    "trace_id": trace_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

    async def list_available_agents(self) -> list[dict[str, Any]]:
        """
        List all available agent types with their configurations.

        Returns:
            List of agent information dictionaries
        """
        agents = []
        for agent_type in AgentType:
            config = get_agent_config(agent_type)
            description = config.instructions
            if len(description) > 200:
                description = description[:200] + "..."
            agents.append({
                "type": agent_type.value,
                "name": config.name,
                "description": description,
                "model": config.model_settings.model,
            })
        return agents

    async def get_session_history(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> dict[str, Any]:
        """
        Get the history for a specific session.

        Args:
            user_id: The user's ID
            session_id: The session ID

        Returns:
            Session information with messages
        """
        stmt = (
            select(Session)
            .options(selectinload(Session.messages))
            .where(
                Session.id == session_id,
                Session.user_id == user_id,
                Session.is_deleted == False,
            )
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError("Session", str(session_id))

        messages = [
            {
                "id": str(msg.id),
                "role": msg.role.value,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "tool_name": msg.tool_name,
                "metadata": msg.message_metadata,
            }
            for msg in sorted(session.messages, key=lambda m: m.created_at)
        ]

        return {
            "id": str(session.id),
            "title": session.title,
            "context": session.context,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "messages": messages,
        }

    async def list_user_sessions(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List all sessions for a user.

        Args:
            user_id: The user's ID
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            Dictionary with sessions list and total count
        """
        # Get total count
        count_stmt = (
            select(func.count(Session.id))
            .where(
                Session.user_id == user_id,
                Session.is_deleted == False,
            )
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Get sessions with message counts
        # Use a subquery to count messages per session
        message_count_subq = (
            select(
                ChatMessage.session_id,
                func.count(ChatMessage.id).label("message_count"),
            )
            .group_by(ChatMessage.session_id)
            .subquery()
        )

        stmt = (
            select(Session, message_count_subq.c.message_count)
            .outerjoin(
                message_count_subq,
                Session.id == message_count_subq.c.session_id,
            )
            .where(
                Session.user_id == user_id,
                Session.is_deleted == False,
            )
            .order_by(Session.last_activity_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        sessions = [
            {
                "id": str(row.Session.id),
                "title": row.Session.title,
                "context": row.Session.context,
                "created_at": row.Session.created_at.isoformat(),
                "last_activity_at": row.Session.last_activity_at.isoformat(),
                "message_count": row.message_count or 0,
            }
            for row in rows
        ]

        return {
            "sessions": sessions,
            "total": total,
        }

    async def update_session(
        self,
        user_id: UUID,
        session_id: UUID,
        title: str | None = None,
    ) -> dict[str, Any]:
        """
        Update a session's properties.

        Args:
            user_id: The user's ID
            session_id: The session ID
            title: New session title (optional)

        Returns:
            Updated session information
        """
        stmt = select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.is_deleted == False,
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError("Session", str(session_id))

        if title is not None:
            session.title = title

        session.update_activity()
        await self.db.flush()

        # Get message count
        count_stmt = (
            select(func.count(ChatMessage.id))
            .where(ChatMessage.session_id == session_id)
        )
        count_result = await self.db.execute(count_stmt)
        message_count = count_result.scalar() or 0

        logger.info(
            "Updated session",
            session_id=str(session_id),
            user_id=str(user_id),
            title=title,
        )

        return {
            "id": str(session.id),
            "title": session.title,
            "context": session.context,
            "created_at": session.created_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "message_count": message_count,
        }

    async def delete_session(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> None:
        """
        Soft-delete a session.

        Args:
            user_id: The user's ID
            session_id: The session ID
        """
        stmt = select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.is_deleted == False,
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise NotFoundError("Session", str(session_id))

        # Soft delete
        session.is_deleted = True
        session.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "Deleted session",
            session_id=str(session_id),
            user_id=str(user_id),
        )


# Dependency injection helper for FastAPI
async def get_agent_service(db: AsyncSession) -> AgentService:
    """
    FastAPI dependency for getting an AgentService instance.

    Args:
        db: Database session from get_db dependency

    Returns:
        Configured AgentService instance
    """
    return AgentService(db)
