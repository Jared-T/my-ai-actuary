"""
Knowledge base service for managing actuarial methods, templates, and precedents.

Provides CRUD operations and semantic search capabilities for the knowledge base,
enabling agents to retrieve relevant information based on context and queries.
"""

import time
from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import and_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from models.knowledge_base import (
    ActuarialMethod,
    KnowledgeBaseCategory,
    KnowledgeBaseSearchLog,
    KnowledgeBaseStatus,
    KnowledgeBaseType,
    Precedent,
    Template,
)
from services.embedding_service import EmbeddingService, get_embedding_service

logger = get_logger(__name__)

# Type variable for generic model handling
T = TypeVar("T", ActuarialMethod, Template, Precedent)

# Search result types
SearchResultType = dict[str, Any]


class KnowledgeBaseService:
    """
    Service for knowledge base operations including CRUD and semantic search.

    Supports:
    - Creating and updating knowledge base entries
    - Full-text search using PostgreSQL tsvector
    - Semantic search using vector embeddings
    - Hybrid search combining both approaches
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ):
        """
        Initialize the knowledge base service.

        Args:
            db: Async database session
            embedding_service: Optional embedding service instance
        """
        self.db = db
        self._embedding_service = embedding_service

    @property
    def embedding_service(self) -> EmbeddingService:
        """Lazy-initialize embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    # ==================== Actuarial Methods ====================

    async def create_method(
        self,
        name: str,
        code: str,
        category: KnowledgeBaseCategory,
        summary: str,
        description: str,
        user_id: UUID | None = None,
        use_cases: str | None = None,
        mathematical_formulation: str | None = None,
        implementation_guidance: str | None = None,
        limitations: str | None = None,
        tags: list[str] | None = None,
        related_standards: list[str] | None = None,
        generate_embedding: bool = True,
    ) -> ActuarialMethod:
        """
        Create a new actuarial method entry.

        Args:
            name: Method name
            code: Short code for the method
            category: Method category
            summary: Brief summary
            description: Detailed description
            user_id: Creating user ID
            use_cases: Typical use cases
            mathematical_formulation: Mathematical formulas
            implementation_guidance: Implementation steps
            limitations: Known limitations
            tags: Tags for categorization
            related_standards: Related regulatory standards
            generate_embedding: Whether to generate embedding

        Returns:
            Created ActuarialMethod instance
        """
        method = ActuarialMethod(
            name=name,
            code=code,
            category=category,
            summary=summary,
            description=description,
            use_cases=use_cases,
            mathematical_formulation=mathematical_formulation,
            implementation_guidance=implementation_guidance,
            limitations=limitations,
            tags=tags,
            related_standards=related_standards,
            created_by=user_id,
            updated_by=user_id,
        )

        self.db.add(method)
        await self.db.flush()

        # Generate embedding if requested
        if generate_embedding:
            await self._update_method_embedding(method)

        logger.info(
            "Created actuarial method",
            method_id=str(method.id),
            code=code,
            name=name,
        )

        return method

    async def update_method(
        self,
        method_id: UUID,
        user_id: UUID | None = None,
        regenerate_embedding: bool = True,
        **updates: Any,
    ) -> ActuarialMethod | None:
        """
        Update an actuarial method entry.

        Args:
            method_id: Method ID
            user_id: Updating user ID
            regenerate_embedding: Whether to regenerate embedding
            **updates: Fields to update

        Returns:
            Updated method or None if not found
        """
        method = await self.get_method(method_id)
        if not method:
            return None

        # Apply updates
        content_changed = False
        for key, value in updates.items():
            if hasattr(method, key):
                old_value = getattr(method, key)
                if old_value != value:
                    setattr(method, key, value)
                    # Track if content fields changed
                    if key in ("name", "summary", "description", "use_cases", "tags"):
                        content_changed = True

        method.updated_by = user_id
        method.updated_at = datetime.now(timezone.utc)

        # Regenerate embedding if content changed
        if regenerate_embedding and content_changed:
            await self._update_method_embedding(method)

        logger.info(
            "Updated actuarial method",
            method_id=str(method_id),
            content_changed=content_changed,
        )

        return method

    async def get_method(self, method_id: UUID) -> ActuarialMethod | None:
        """Get a method by ID."""
        result = await self.db.execute(
            select(ActuarialMethod).where(
                and_(
                    ActuarialMethod.id == method_id,
                    ActuarialMethod.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_method_by_code(self, code: str) -> ActuarialMethod | None:
        """Get a method by code."""
        result = await self.db.execute(
            select(ActuarialMethod).where(
                and_(
                    ActuarialMethod.code == code,
                    ActuarialMethod.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_methods(
        self,
        category: KnowledgeBaseCategory | None = None,
        status: KnowledgeBaseStatus | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActuarialMethod]:
        """
        List actuarial methods with optional filtering.

        Args:
            category: Filter by category
            status: Filter by status
            tags: Filter by tags (any match)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of matching methods
        """
        query = select(ActuarialMethod).where(ActuarialMethod.is_deleted == False)

        if category:
            query = query.where(ActuarialMethod.category == category)

        if status:
            query = query.where(ActuarialMethod.status == status)
        else:
            # Default to active methods
            query = query.where(ActuarialMethod.status == KnowledgeBaseStatus.ACTIVE)

        if tags:
            # Match any of the provided tags
            query = query.where(ActuarialMethod.tags.overlap(tags))

        query = query.order_by(
            ActuarialMethod.search_priority.desc(),
            ActuarialMethod.usage_count.desc(),
            ActuarialMethod.name,
        ).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _update_method_embedding(self, method: ActuarialMethod) -> None:
        """Generate and store embedding for a method."""
        text = self.embedding_service.prepare_method_text(
            name=method.name,
            summary=method.summary,
            description=method.description,
            use_cases=method.use_cases,
            implementation_guidance=method.implementation_guidance,
            tags=method.tags,
        )

        embedding = await self.embedding_service.generate_embedding(text)
        method.embedding = self.embedding_service.embedding_to_json(embedding)
        method.embedding_model = self.embedding_service.model
        method.embedding_updated_at = datetime.now(timezone.utc)

    # ==================== Templates ====================

    async def create_template(
        self,
        name: str,
        code: str,
        category: KnowledgeBaseCategory,
        summary: str,
        description: str,
        user_id: UUID | None = None,
        template_type: KnowledgeBaseType = KnowledgeBaseType.TEMPLATE,
        structure: dict | None = None,
        required_inputs: dict | None = None,
        output_format: str | None = None,
        content: str | None = None,
        storage_path: str | None = None,
        tags: list[str] | None = None,
        generate_embedding: bool = True,
    ) -> Template:
        """Create a new template entry."""
        template = Template(
            name=name,
            code=code,
            template_type=template_type,
            category=category,
            summary=summary,
            description=description,
            structure=structure,
            required_inputs=required_inputs,
            output_format=output_format,
            content=content,
            storage_path=storage_path,
            tags=tags,
            created_by=user_id,
            updated_by=user_id,
        )

        self.db.add(template)
        await self.db.flush()

        if generate_embedding:
            await self._update_template_embedding(template)

        logger.info(
            "Created template",
            template_id=str(template.id),
            code=code,
            name=name,
        )

        return template

    async def get_template(self, template_id: UUID) -> Template | None:
        """Get a template by ID."""
        result = await self.db.execute(
            select(Template).where(
                and_(
                    Template.id == template_id,
                    Template.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_template_by_code(self, code: str) -> Template | None:
        """Get a template by code."""
        result = await self.db.execute(
            select(Template).where(
                and_(
                    Template.code == code,
                    Template.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        category: KnowledgeBaseCategory | None = None,
        template_type: KnowledgeBaseType | None = None,
        status: KnowledgeBaseStatus | None = None,
        output_format: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Template]:
        """List templates with optional filtering."""
        query = select(Template).where(Template.is_deleted == False)

        if category:
            query = query.where(Template.category == category)

        if template_type:
            query = query.where(Template.template_type == template_type)

        if status:
            query = query.where(Template.status == status)
        else:
            query = query.where(Template.status == KnowledgeBaseStatus.ACTIVE)

        if output_format:
            query = query.where(Template.output_format == output_format)

        if tags:
            query = query.where(Template.tags.overlap(tags))

        query = query.order_by(
            Template.search_priority.desc(),
            Template.usage_count.desc(),
            Template.name,
        ).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _update_template_embedding(self, template: Template) -> None:
        """Generate and store embedding for a template."""
        text = self.embedding_service.prepare_template_text(
            name=template.name,
            summary=template.summary,
            description=template.description,
            output_format=template.output_format,
            tags=template.tags,
        )

        embedding = await self.embedding_service.generate_embedding(text)
        template.embedding = self.embedding_service.embedding_to_json(embedding)
        template.embedding_model = self.embedding_service.model
        template.embedding_updated_at = datetime.now(timezone.utc)

    # ==================== Precedents ====================

    async def create_precedent(
        self,
        title: str,
        reference_code: str,
        category: KnowledgeBaseCategory,
        summary: str,
        description: str,
        user_id: UUID | None = None,
        context: str | None = None,
        industry: str | None = None,
        jurisdiction: str | None = None,
        reporting_period: str | None = None,
        methods_used: list[str] | None = None,
        approach_description: str | None = None,
        outcome: str | None = None,
        lessons_learned: str | None = None,
        related_artefacts: dict | None = None,
        tags: list[str] | None = None,
        confidentiality_level: str = "internal",
        is_anonymized: bool = True,
        generate_embedding: bool = True,
    ) -> Precedent:
        """Create a new precedent entry."""
        precedent = Precedent(
            title=title,
            reference_code=reference_code,
            category=category,
            summary=summary,
            description=description,
            context=context,
            industry=industry,
            jurisdiction=jurisdiction,
            reporting_period=reporting_period,
            methods_used=methods_used,
            approach_description=approach_description,
            outcome=outcome,
            lessons_learned=lessons_learned,
            related_artefacts=related_artefacts,
            tags=tags,
            confidentiality_level=confidentiality_level,
            is_anonymized=is_anonymized,
            created_by=user_id,
            updated_by=user_id,
        )

        self.db.add(precedent)
        await self.db.flush()

        if generate_embedding:
            await self._update_precedent_embedding(precedent)

        logger.info(
            "Created precedent",
            precedent_id=str(precedent.id),
            reference_code=reference_code,
            title=title,
        )

        return precedent

    async def get_precedent(self, precedent_id: UUID) -> Precedent | None:
        """Get a precedent by ID."""
        result = await self.db.execute(
            select(Precedent).where(
                and_(
                    Precedent.id == precedent_id,
                    Precedent.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_precedent_by_reference(self, reference_code: str) -> Precedent | None:
        """Get a precedent by reference code."""
        result = await self.db.execute(
            select(Precedent).where(
                and_(
                    Precedent.reference_code == reference_code,
                    Precedent.is_deleted == False,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_precedents(
        self,
        category: KnowledgeBaseCategory | None = None,
        industry: str | None = None,
        jurisdiction: str | None = None,
        methods_used: list[str] | None = None,
        status: KnowledgeBaseStatus | None = None,
        confidentiality_level: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Precedent]:
        """List precedents with optional filtering."""
        query = select(Precedent).where(Precedent.is_deleted == False)

        if category:
            query = query.where(Precedent.category == category)

        if industry:
            query = query.where(Precedent.industry == industry)

        if jurisdiction:
            query = query.where(Precedent.jurisdiction == jurisdiction)

        if methods_used:
            query = query.where(Precedent.methods_used.overlap(methods_used))

        if status:
            query = query.where(Precedent.status == status)
        else:
            query = query.where(Precedent.status == KnowledgeBaseStatus.ACTIVE)

        if confidentiality_level:
            query = query.where(Precedent.confidentiality_level == confidentiality_level)

        if tags:
            query = query.where(Precedent.tags.overlap(tags))

        query = query.order_by(
            Precedent.search_priority.desc(),
            Precedent.relevance_score.desc().nullsfirst(),
            Precedent.usage_count.desc(),
            Precedent.title,
        ).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _update_precedent_embedding(self, precedent: Precedent) -> None:
        """Generate and store embedding for a precedent."""
        text = self.embedding_service.prepare_precedent_text(
            title=precedent.title,
            summary=precedent.summary,
            description=precedent.description,
            context=precedent.context,
            industry=precedent.industry,
            methods_used=precedent.methods_used,
            outcome=precedent.outcome,
            lessons_learned=precedent.lessons_learned,
            tags=precedent.tags,
        )

        embedding = await self.embedding_service.generate_embedding(text)
        precedent.embedding = self.embedding_service.embedding_to_json(embedding)
        precedent.embedding_model = self.embedding_service.model
        precedent.embedding_updated_at = datetime.now(timezone.utc)

    # ==================== Search Operations ====================

    async def search(
        self,
        query: str,
        search_types: list[str] | None = None,
        category: KnowledgeBaseCategory | None = None,
        limit: int = 10,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[SearchResultType]:
        """
        Perform semantic search across the knowledge base.

        Args:
            query: Search query text
            search_types: Types to search (method, template, precedent)
            category: Filter by category
            limit: Maximum results per type
            user_id: User ID for logging
            session_id: Session ID for logging

        Returns:
            List of search results with scores
        """
        start_time = time.time()

        if not search_types:
            search_types = ["method", "template", "precedent"]

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        results: list[SearchResultType] = []

        # Search each type
        if "method" in search_types:
            method_results = await self._search_methods_semantic(
                query_embedding, category, limit
            )
            results.extend(method_results)

        if "template" in search_types:
            template_results = await self._search_templates_semantic(
                query_embedding, category, limit
            )
            results.extend(template_results)

        if "precedent" in search_types:
            precedent_results = await self._search_precedents_semantic(
                query_embedding, category, limit
            )
            results.extend(precedent_results)

        # Sort by similarity score and limit
        results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        results = results[:limit]

        # Calculate search duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log search
        await self._log_search(
            query=query,
            search_type="semantic",
            filters={"category": category.value if category else None, "types": search_types},
            result_count=len(results),
            result_ids=[r["id"] for r in results],
            top_result_type=results[0]["type"] if results else None,
            duration_ms=duration_ms,
            user_id=user_id,
            session_id=session_id,
        )

        return results

    async def _search_methods_semantic(
        self,
        query_embedding: list[float],
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Search methods using semantic similarity."""
        query = select(ActuarialMethod).where(
            and_(
                ActuarialMethod.is_deleted == False,
                ActuarialMethod.status == KnowledgeBaseStatus.ACTIVE,
                ActuarialMethod.embedding.isnot(None),
            )
        )

        if category:
            query = query.where(ActuarialMethod.category == category)

        query = query.limit(limit * 3)  # Get more results for reranking

        result = await self.db.execute(query)
        methods = result.scalars().all()

        # Calculate similarities and rank
        results: list[SearchResultType] = []
        for method in methods:
            if method.embedding:
                method_embedding = self.embedding_service.json_to_embedding(method.embedding)
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, method_embedding
                )

                results.append({
                    "id": str(method.id),
                    "type": "method",
                    "name": method.name,
                    "code": method.code,
                    "category": method.category.value,
                    "summary": method.summary,
                    "tags": method.tags,
                    "similarity_score": similarity,
                })

        # Sort by similarity and limit
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]

    async def _search_templates_semantic(
        self,
        query_embedding: list[float],
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Search templates using semantic similarity."""
        query = select(Template).where(
            and_(
                Template.is_deleted == False,
                Template.status == KnowledgeBaseStatus.ACTIVE,
                Template.embedding.isnot(None),
            )
        )

        if category:
            query = query.where(Template.category == category)

        query = query.limit(limit * 3)

        result = await self.db.execute(query)
        templates = result.scalars().all()

        results: list[SearchResultType] = []
        for template in templates:
            if template.embedding:
                template_embedding = self.embedding_service.json_to_embedding(template.embedding)
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, template_embedding
                )

                results.append({
                    "id": str(template.id),
                    "type": "template",
                    "name": template.name,
                    "code": template.code,
                    "category": template.category.value,
                    "summary": template.summary,
                    "output_format": template.output_format,
                    "tags": template.tags,
                    "similarity_score": similarity,
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]

    async def _search_precedents_semantic(
        self,
        query_embedding: list[float],
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Search precedents using semantic similarity."""
        query = select(Precedent).where(
            and_(
                Precedent.is_deleted == False,
                Precedent.status == KnowledgeBaseStatus.ACTIVE,
                Precedent.embedding.isnot(None),
            )
        )

        if category:
            query = query.where(Precedent.category == category)

        query = query.limit(limit * 3)

        result = await self.db.execute(query)
        precedents = result.scalars().all()

        results: list[SearchResultType] = []
        for precedent in precedents:
            if precedent.embedding:
                precedent_embedding = self.embedding_service.json_to_embedding(precedent.embedding)
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, precedent_embedding
                )

                results.append({
                    "id": str(precedent.id),
                    "type": "precedent",
                    "title": precedent.title,
                    "reference_code": precedent.reference_code,
                    "category": precedent.category.value,
                    "summary": precedent.summary,
                    "industry": precedent.industry,
                    "methods_used": precedent.methods_used,
                    "tags": precedent.tags,
                    "similarity_score": similarity,
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]

    async def search_fulltext(
        self,
        query: str,
        search_types: list[str] | None = None,
        category: KnowledgeBaseCategory | None = None,
        limit: int = 10,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[SearchResultType]:
        """
        Perform full-text search across the knowledge base.

        Uses PostgreSQL full-text search for keyword matching.
        """
        start_time = time.time()

        if not search_types:
            search_types = ["method", "template", "precedent"]

        results: list[SearchResultType] = []

        # Prepare search query for PostgreSQL
        search_terms = query.replace(" ", " & ")

        if "method" in search_types:
            method_results = await self._search_methods_fulltext(
                search_terms, category, limit
            )
            results.extend(method_results)

        if "template" in search_types:
            template_results = await self._search_templates_fulltext(
                search_terms, category, limit
            )
            results.extend(template_results)

        if "precedent" in search_types:
            precedent_results = await self._search_precedents_fulltext(
                search_terms, category, limit
            )
            results.extend(precedent_results)

        # Sort by rank score and limit
        results.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
        results = results[:limit]

        duration_ms = int((time.time() - start_time) * 1000)

        await self._log_search(
            query=query,
            search_type="fulltext",
            filters={"category": category.value if category else None, "types": search_types},
            result_count=len(results),
            result_ids=[r["id"] for r in results],
            top_result_type=results[0]["type"] if results else None,
            duration_ms=duration_ms,
            user_id=user_id,
            session_id=session_id,
        )

        return results

    async def _search_methods_fulltext(
        self,
        search_terms: str,
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Full-text search on methods."""
        sql = text("""
            SELECT
                id, name, code, category, summary, tags,
                ts_rank(
                    to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')),
                    plainto_tsquery('english', :query)
                ) as rank
            FROM actuarial_methods
            WHERE is_deleted = false
                AND status = 'active'
                AND to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, ''))
                    @@ plainto_tsquery('english', :query)
                AND (:category IS NULL OR category = :category)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            sql,
            {
                "query": search_terms.replace(" & ", " "),
                "category": category.value if category else None,
                "limit": limit,
            },
        )

        results: list[SearchResultType] = []
        for row in result:
            results.append({
                "id": str(row.id),
                "type": "method",
                "name": row.name,
                "code": row.code,
                "category": row.category,
                "summary": row.summary,
                "tags": row.tags,
                "rank_score": float(row.rank),
            })

        return results

    async def _search_templates_fulltext(
        self,
        search_terms: str,
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Full-text search on templates."""
        sql = text("""
            SELECT
                id, name, code, category, summary, output_format, tags,
                ts_rank(
                    to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')),
                    plainto_tsquery('english', :query)
                ) as rank
            FROM templates
            WHERE is_deleted = false
                AND status = 'active'
                AND to_tsvector('english', name || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, ''))
                    @@ plainto_tsquery('english', :query)
                AND (:category IS NULL OR category = :category)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            sql,
            {
                "query": search_terms.replace(" & ", " "),
                "category": category.value if category else None,
                "limit": limit,
            },
        )

        results: list[SearchResultType] = []
        for row in result:
            results.append({
                "id": str(row.id),
                "type": "template",
                "name": row.name,
                "code": row.code,
                "category": row.category,
                "summary": row.summary,
                "output_format": row.output_format,
                "tags": row.tags,
                "rank_score": float(row.rank),
            })

        return results

    async def _search_precedents_fulltext(
        self,
        search_terms: str,
        category: KnowledgeBaseCategory | None,
        limit: int,
    ) -> list[SearchResultType]:
        """Full-text search on precedents."""
        sql = text("""
            SELECT
                id, title, reference_code, category, summary, industry, methods_used, tags,
                ts_rank(
                    to_tsvector('english', title || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, '')),
                    plainto_tsquery('english', :query)
                ) as rank
            FROM precedents
            WHERE is_deleted = false
                AND status = 'active'
                AND to_tsvector('english', title || ' ' || COALESCE(summary, '') || ' ' || COALESCE(description, ''))
                    @@ plainto_tsquery('english', :query)
                AND (:category IS NULL OR category = :category)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await self.db.execute(
            sql,
            {
                "query": search_terms.replace(" & ", " "),
                "category": category.value if category else None,
                "limit": limit,
            },
        )

        results: list[SearchResultType] = []
        for row in result:
            results.append({
                "id": str(row.id),
                "type": "precedent",
                "title": row.title,
                "reference_code": row.reference_code,
                "category": row.category,
                "summary": row.summary,
                "industry": row.industry,
                "methods_used": row.methods_used,
                "tags": row.tags,
                "rank_score": float(row.rank),
            })

        return results

    async def search_hybrid(
        self,
        query: str,
        search_types: list[str] | None = None,
        category: KnowledgeBaseCategory | None = None,
        limit: int = 10,
        semantic_weight: float = 0.7,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[SearchResultType]:
        """
        Perform hybrid search combining semantic and full-text search.

        Args:
            query: Search query
            search_types: Types to search
            category: Filter by category
            limit: Maximum results
            semantic_weight: Weight for semantic scores (0-1)
            user_id: User ID for logging
            session_id: Session ID for logging

        Returns:
            Combined and ranked search results
        """
        start_time = time.time()

        # Get results from both search methods
        semantic_results = await self.search(
            query, search_types, category, limit * 2,
            user_id=None, session_id=None  # Don't log individual searches
        )
        fulltext_results = await self.search_fulltext(
            query, search_types, category, limit * 2,
            user_id=None, session_id=None
        )

        # Combine and score results
        combined: dict[str, SearchResultType] = {}

        # Process semantic results
        for result in semantic_results:
            result_id = result["id"]
            combined[result_id] = result.copy()
            combined[result_id]["semantic_score"] = result.get("similarity_score", 0)
            combined[result_id]["fulltext_score"] = 0

        # Process fulltext results
        for result in fulltext_results:
            result_id = result["id"]
            if result_id in combined:
                combined[result_id]["fulltext_score"] = result.get("rank_score", 0)
            else:
                combined[result_id] = result.copy()
                combined[result_id]["semantic_score"] = 0
                combined[result_id]["fulltext_score"] = result.get("rank_score", 0)

        # Calculate combined scores
        fulltext_weight = 1 - semantic_weight
        for result in combined.values():
            # Normalize scores
            semantic_score = result.get("semantic_score", 0)
            fulltext_score = result.get("fulltext_score", 0)

            # Combined score
            result["combined_score"] = (
                semantic_weight * semantic_score +
                fulltext_weight * min(fulltext_score, 1.0)  # Cap fulltext score at 1
            )

        # Sort and limit
        results = sorted(
            combined.values(),
            key=lambda x: x.get("combined_score", 0),
            reverse=True,
        )[:limit]

        duration_ms = int((time.time() - start_time) * 1000)

        await self._log_search(
            query=query,
            search_type="hybrid",
            filters={
                "category": category.value if category else None,
                "types": search_types,
                "semantic_weight": semantic_weight,
            },
            result_count=len(results),
            result_ids=[r["id"] for r in results],
            top_result_type=results[0]["type"] if results else None,
            duration_ms=duration_ms,
            user_id=user_id,
            session_id=session_id,
        )

        return results

    # ==================== Usage Tracking ====================

    async def increment_usage(
        self,
        item_type: str,
        item_id: UUID,
    ) -> None:
        """Increment usage count for a knowledge base item."""
        if item_type == "method":
            await self.db.execute(
                update(ActuarialMethod)
                .where(ActuarialMethod.id == item_id)
                .values(usage_count=ActuarialMethod.usage_count + 1)
            )
        elif item_type == "template":
            await self.db.execute(
                update(Template)
                .where(Template.id == item_id)
                .values(usage_count=Template.usage_count + 1)
            )
        elif item_type == "precedent":
            await self.db.execute(
                update(Precedent)
                .where(Precedent.id == item_id)
                .values(usage_count=Precedent.usage_count + 1)
            )

    async def _log_search(
        self,
        query: str,
        search_type: str,
        filters: dict | None,
        result_count: int,
        result_ids: list[str],
        top_result_type: str | None,
        duration_ms: int,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> None:
        """Log a search query for analytics."""
        log_entry = KnowledgeBaseSearchLog(
            user_id=user_id,
            session_id=session_id,
            query=query,
            search_type=search_type,
            filters_applied=filters,
            result_count=result_count,
            result_ids=result_ids,
            top_result_type=top_result_type,
            search_duration_ms=duration_ms,
        )

        self.db.add(log_entry)

        logger.debug(
            "Knowledge base search",
            query=query[:100],
            search_type=search_type,
            result_count=result_count,
            duration_ms=duration_ms,
        )

    async def record_search_feedback(
        self,
        search_log_id: UUID,
        clicked_result_id: UUID | None = None,
        helpful: bool | None = None,
        notes: str | None = None,
    ) -> None:
        """Record user feedback on search results."""
        await self.db.execute(
            update(KnowledgeBaseSearchLog)
            .where(KnowledgeBaseSearchLog.id == search_log_id)
            .values(
                clicked_result_id=clicked_result_id,
                feedback_helpful=helpful,
                feedback_notes=notes,
            )
        )
