"""
Knowledge base API routes for actuarial methods, templates, and precedents.

Provides endpoints for:
- CRUD operations on knowledge base entries
- Semantic search across the knowledge base
- Full-text search capabilities
- Usage tracking and analytics
"""

from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import CurrentUser, OptionalUser
from core.database import get_db
from models.knowledge_base import KnowledgeBaseCategory, KnowledgeBaseStatus, KnowledgeBaseType
from services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])


# ==================== Request/Response Models ====================

class MethodCreateRequest(BaseModel):
    """Request model for creating an actuarial method."""

    name: str = Field(..., min_length=1, max_length=255, description="Method name")
    code: str = Field(..., min_length=1, max_length=50, description="Short code")
    category: KnowledgeBaseCategory = Field(..., description="Method category")
    summary: str = Field(..., min_length=1, description="Brief summary")
    description: str = Field(..., min_length=1, description="Detailed description")
    use_cases: str | None = Field(default=None, description="Typical use cases")
    mathematical_formulation: str | None = Field(default=None, description="Mathematical formulas")
    implementation_guidance: str | None = Field(default=None, description="Implementation steps")
    limitations: str | None = Field(default=None, description="Known limitations")
    tags: list[str] | None = Field(default=None, description="Tags for categorization")
    related_standards: list[str] | None = Field(default=None, description="Related standards")


class MethodUpdateRequest(BaseModel):
    """Request model for updating an actuarial method."""

    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    description: str | None = None
    use_cases: str | None = None
    mathematical_formulation: str | None = None
    implementation_guidance: str | None = None
    limitations: str | None = None
    tags: list[str] | None = None
    related_standards: list[str] | None = None
    status: KnowledgeBaseStatus | None = None


class MethodResponse(BaseModel):
    """Response model for an actuarial method."""

    id: str
    name: str
    code: str
    category: str
    summary: str
    description: str
    use_cases: str | None = None
    mathematical_formulation: str | None = None
    implementation_guidance: str | None = None
    limitations: str | None = None
    tags: list[str] | None = None
    related_standards: list[str] | None = None
    status: str
    version: str
    usage_count: int
    created_at: str


class TemplateCreateRequest(BaseModel):
    """Request model for creating a template."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    category: KnowledgeBaseCategory
    summary: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    template_type: KnowledgeBaseType = Field(default=KnowledgeBaseType.TEMPLATE)
    structure: dict | None = None
    required_inputs: dict | None = None
    output_format: str | None = None
    content: str | None = None
    storage_path: str | None = None
    tags: list[str] | None = None


class TemplateResponse(BaseModel):
    """Response model for a template."""

    id: str
    name: str
    code: str
    template_type: str
    category: str
    summary: str
    description: str
    structure: dict | None = None
    required_inputs: dict | None = None
    output_format: str | None = None
    tags: list[str] | None = None
    status: str
    version: str
    usage_count: int
    created_at: str


class PrecedentCreateRequest(BaseModel):
    """Request model for creating a precedent."""

    title: str = Field(..., min_length=1, max_length=255)
    reference_code: str = Field(..., min_length=1, max_length=100)
    category: KnowledgeBaseCategory
    summary: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    context: str | None = None
    industry: str | None = None
    jurisdiction: str | None = None
    reporting_period: str | None = None
    methods_used: list[str] | None = None
    approach_description: str | None = None
    outcome: str | None = None
    lessons_learned: str | None = None
    related_artefacts: dict | None = None
    tags: list[str] | None = None
    confidentiality_level: str = Field(default="internal")
    is_anonymized: bool = Field(default=True)


class PrecedentResponse(BaseModel):
    """Response model for a precedent."""

    id: str
    title: str
    reference_code: str
    category: str
    summary: str
    description: str
    context: str | None = None
    industry: str | None = None
    jurisdiction: str | None = None
    reporting_period: str | None = None
    methods_used: list[str] | None = None
    approach_description: str | None = None
    outcome: str | None = None
    lessons_learned: str | None = None
    tags: list[str] | None = None
    confidentiality_level: str
    is_anonymized: bool
    status: str
    usage_count: int
    created_at: str


class SearchMode(str, PyEnum):
    """Valid search modes for knowledge base search."""
    SEMANTIC = "semantic"
    FULLTEXT = "fulltext"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    """Request model for knowledge base search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    search_types: list[str] | None = Field(
        default=None,
        description="Types to search (method, template, precedent)",
    )
    category: KnowledgeBaseCategory | None = Field(default=None)
    limit: int = Field(default=10, ge=1, le=50)
    search_mode: SearchMode = Field(
        default=SearchMode.HYBRID,
        description="Search mode: semantic, fulltext, or hybrid",
    )


class SearchResult(BaseModel):
    """Single search result."""

    id: str
    type: str
    name: str | None = None
    title: str | None = None
    code: str | None = None
    reference_code: str | None = None
    category: str
    summary: str
    tags: list[str] | None = None
    similarity_score: float | None = None
    rank_score: float | None = None
    combined_score: float | None = None


class SearchResponse(BaseModel):
    """Response model for search results."""

    query: str
    search_mode: SearchMode
    result_count: int
    results: list[SearchResult]


# ==================== Method Endpoints ====================

@router.post(
    "/methods",
    response_model=MethodResponse,
    summary="Create actuarial method",
    description="Create a new actuarial method entry in the knowledge base.",
)
async def create_method(
    request: MethodCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MethodResponse:
    """Create a new actuarial method."""
    service = KnowledgeBaseService(db)

    try:
        method = await service.create_method(
            name=request.name,
            code=request.code,
            category=request.category,
            summary=request.summary,
            description=request.description,
            user_id=current_user.id,
            use_cases=request.use_cases,
            mathematical_formulation=request.mathematical_formulation,
            implementation_guidance=request.implementation_guidance,
            limitations=request.limitations,
            tags=request.tags,
            related_standards=request.related_standards,
        )

        return MethodResponse(
            id=str(method.id),
            name=method.name,
            code=method.code,
            category=method.category.value,
            summary=method.summary,
            description=method.description,
            use_cases=method.use_cases,
            mathematical_formulation=method.mathematical_formulation,
            implementation_guidance=method.implementation_guidance,
            limitations=method.limitations,
            tags=method.tags,
            related_standards=method.related_standards,
            status=method.status.value,
            version=method.version,
            usage_count=method.usage_count,
            created_at=method.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/methods",
    response_model=list[MethodResponse],
    summary="List actuarial methods",
    description="List actuarial methods with optional filtering.",
)
async def list_methods(
    category: KnowledgeBaseCategory | None = None,
    status: KnowledgeBaseStatus | None = None,
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MethodResponse]:
    """List actuarial methods."""
    service = KnowledgeBaseService(db)
    methods = await service.list_methods(
        category=category,
        status=status,
        tags=tags,
        limit=limit,
        offset=offset,
    )

    return [
        MethodResponse(
            id=str(m.id),
            name=m.name,
            code=m.code,
            category=m.category.value,
            summary=m.summary,
            description=m.description,
            use_cases=m.use_cases,
            mathematical_formulation=m.mathematical_formulation,
            implementation_guidance=m.implementation_guidance,
            limitations=m.limitations,
            tags=m.tags,
            related_standards=m.related_standards,
            status=m.status.value,
            version=m.version,
            usage_count=m.usage_count,
            created_at=m.created_at.isoformat(),
        )
        for m in methods
    ]


@router.get(
    "/methods/{method_id}",
    response_model=MethodResponse,
    summary="Get actuarial method",
    description="Get a specific actuarial method by ID.",
)
async def get_method(
    method_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MethodResponse:
    """Get an actuarial method by ID."""
    service = KnowledgeBaseService(db)
    method = await service.get_method(method_id)

    if not method:
        raise HTTPException(status_code=404, detail="Method not found")

    # Increment usage count
    await service.increment_usage("method", method_id)

    return MethodResponse(
        id=str(method.id),
        name=method.name,
        code=method.code,
        category=method.category.value,
        summary=method.summary,
        description=method.description,
        use_cases=method.use_cases,
        mathematical_formulation=method.mathematical_formulation,
        implementation_guidance=method.implementation_guidance,
        limitations=method.limitations,
        tags=method.tags,
        related_standards=method.related_standards,
        status=method.status.value,
        version=method.version,
        usage_count=method.usage_count,
        created_at=method.created_at.isoformat(),
    )


@router.get(
    "/methods/code/{code}",
    response_model=MethodResponse,
    summary="Get method by code",
    description="Get a specific actuarial method by its code.",
)
async def get_method_by_code(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> MethodResponse:
    """Get an actuarial method by code."""
    service = KnowledgeBaseService(db)
    method = await service.get_method_by_code(code)

    if not method:
        raise HTTPException(status_code=404, detail="Method not found")

    await service.increment_usage("method", method.id)

    return MethodResponse(
        id=str(method.id),
        name=method.name,
        code=method.code,
        category=method.category.value,
        summary=method.summary,
        description=method.description,
        use_cases=method.use_cases,
        mathematical_formulation=method.mathematical_formulation,
        implementation_guidance=method.implementation_guidance,
        limitations=method.limitations,
        tags=method.tags,
        related_standards=method.related_standards,
        status=method.status.value,
        version=method.version,
        usage_count=method.usage_count,
        created_at=method.created_at.isoformat(),
    )


@router.patch(
    "/methods/{method_id}",
    response_model=MethodResponse,
    summary="Update actuarial method",
    description="Update an existing actuarial method.",
)
async def update_method(
    method_id: UUID,
    request: MethodUpdateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> MethodResponse:
    """Update an actuarial method."""
    service = KnowledgeBaseService(db)

    updates = request.model_dump(exclude_unset=True)
    method = await service.update_method(
        method_id=method_id,
        user_id=current_user.id,
        **updates,
    )

    if not method:
        raise HTTPException(status_code=404, detail="Method not found")

    return MethodResponse(
        id=str(method.id),
        name=method.name,
        code=method.code,
        category=method.category.value,
        summary=method.summary,
        description=method.description,
        use_cases=method.use_cases,
        mathematical_formulation=method.mathematical_formulation,
        implementation_guidance=method.implementation_guidance,
        limitations=method.limitations,
        tags=method.tags,
        related_standards=method.related_standards,
        status=method.status.value,
        version=method.version,
        usage_count=method.usage_count,
        created_at=method.created_at.isoformat(),
    )


# ==================== Template Endpoints ====================

@router.post(
    "/templates",
    response_model=TemplateResponse,
    summary="Create template",
    description="Create a new template entry in the knowledge base.",
)
async def create_template(
    request: TemplateCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Create a new template."""
    service = KnowledgeBaseService(db)

    try:
        template = await service.create_template(
            name=request.name,
            code=request.code,
            category=request.category,
            summary=request.summary,
            description=request.description,
            user_id=current_user.id,
            template_type=request.template_type,
            structure=request.structure,
            required_inputs=request.required_inputs,
            output_format=request.output_format,
            content=request.content,
            storage_path=request.storage_path,
            tags=request.tags,
        )

        return TemplateResponse(
            id=str(template.id),
            name=template.name,
            code=template.code,
            template_type=template.template_type.value,
            category=template.category.value,
            summary=template.summary,
            description=template.description,
            structure=template.structure,
            required_inputs=template.required_inputs,
            output_format=template.output_format,
            tags=template.tags,
            status=template.status.value,
            version=template.version,
            usage_count=template.usage_count,
            created_at=template.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/templates",
    response_model=list[TemplateResponse],
    summary="List templates",
    description="List templates with optional filtering.",
)
async def list_templates(
    category: KnowledgeBaseCategory | None = None,
    template_type: KnowledgeBaseType | None = None,
    status: KnowledgeBaseStatus | None = None,
    output_format: str | None = None,
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateResponse]:
    """List templates."""
    service = KnowledgeBaseService(db)
    templates = await service.list_templates(
        category=category,
        template_type=template_type,
        status=status,
        output_format=output_format,
        tags=tags,
        limit=limit,
        offset=offset,
    )

    return [
        TemplateResponse(
            id=str(t.id),
            name=t.name,
            code=t.code,
            template_type=t.template_type.value,
            category=t.category.value,
            summary=t.summary,
            description=t.description,
            structure=t.structure,
            required_inputs=t.required_inputs,
            output_format=t.output_format,
            tags=t.tags,
            status=t.status.value,
            version=t.version,
            usage_count=t.usage_count,
            created_at=t.created_at.isoformat(),
        )
        for t in templates
    ]


@router.get(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    summary="Get template",
    description="Get a specific template by ID.",
)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    """Get a template by ID."""
    service = KnowledgeBaseService(db)
    template = await service.get_template(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await service.increment_usage("template", template_id)

    return TemplateResponse(
        id=str(template.id),
        name=template.name,
        code=template.code,
        template_type=template.template_type.value,
        category=template.category.value,
        summary=template.summary,
        description=template.description,
        structure=template.structure,
        required_inputs=template.required_inputs,
        output_format=template.output_format,
        tags=template.tags,
        status=template.status.value,
        version=template.version,
        usage_count=template.usage_count,
        created_at=template.created_at.isoformat(),
    )


# ==================== Precedent Endpoints ====================

@router.post(
    "/precedents",
    response_model=PrecedentResponse,
    summary="Create precedent",
    description="Create a new precedent entry in the knowledge base.",
)
async def create_precedent(
    request: PrecedentCreateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PrecedentResponse:
    """Create a new precedent."""
    service = KnowledgeBaseService(db)

    try:
        precedent = await service.create_precedent(
            title=request.title,
            reference_code=request.reference_code,
            category=request.category,
            summary=request.summary,
            description=request.description,
            user_id=current_user.id,
            context=request.context,
            industry=request.industry,
            jurisdiction=request.jurisdiction,
            reporting_period=request.reporting_period,
            methods_used=request.methods_used,
            approach_description=request.approach_description,
            outcome=request.outcome,
            lessons_learned=request.lessons_learned,
            related_artefacts=request.related_artefacts,
            tags=request.tags,
            confidentiality_level=request.confidentiality_level,
            is_anonymized=request.is_anonymized,
        )

        return PrecedentResponse(
            id=str(precedent.id),
            title=precedent.title,
            reference_code=precedent.reference_code,
            category=precedent.category.value,
            summary=precedent.summary,
            description=precedent.description,
            context=precedent.context,
            industry=precedent.industry,
            jurisdiction=precedent.jurisdiction,
            reporting_period=precedent.reporting_period,
            methods_used=precedent.methods_used,
            approach_description=precedent.approach_description,
            outcome=precedent.outcome,
            lessons_learned=precedent.lessons_learned,
            tags=precedent.tags,
            confidentiality_level=precedent.confidentiality_level,
            is_anonymized=precedent.is_anonymized,
            status=precedent.status.value,
            usage_count=precedent.usage_count,
            created_at=precedent.created_at.isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/precedents",
    response_model=list[PrecedentResponse],
    summary="List precedents",
    description="List precedents with optional filtering.",
)
async def list_precedents(
    category: KnowledgeBaseCategory | None = None,
    industry: str | None = None,
    jurisdiction: str | None = None,
    methods_used: list[str] | None = Query(default=None),
    status: KnowledgeBaseStatus | None = None,
    confidentiality_level: str | None = None,
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[PrecedentResponse]:
    """List precedents."""
    service = KnowledgeBaseService(db)
    precedents = await service.list_precedents(
        category=category,
        industry=industry,
        jurisdiction=jurisdiction,
        methods_used=methods_used,
        status=status,
        confidentiality_level=confidentiality_level,
        tags=tags,
        limit=limit,
        offset=offset,
    )

    return [
        PrecedentResponse(
            id=str(p.id),
            title=p.title,
            reference_code=p.reference_code,
            category=p.category.value,
            summary=p.summary,
            description=p.description,
            context=p.context,
            industry=p.industry,
            jurisdiction=p.jurisdiction,
            reporting_period=p.reporting_period,
            methods_used=p.methods_used,
            approach_description=p.approach_description,
            outcome=p.outcome,
            lessons_learned=p.lessons_learned,
            tags=p.tags,
            confidentiality_level=p.confidentiality_level,
            is_anonymized=p.is_anonymized,
            status=p.status.value,
            usage_count=p.usage_count,
            created_at=p.created_at.isoformat(),
        )
        for p in precedents
    ]


@router.get(
    "/precedents/{precedent_id}",
    response_model=PrecedentResponse,
    summary="Get precedent",
    description="Get a specific precedent by ID.",
)
async def get_precedent(
    precedent_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PrecedentResponse:
    """Get a precedent by ID."""
    service = KnowledgeBaseService(db)
    precedent = await service.get_precedent(precedent_id)

    if not precedent:
        raise HTTPException(status_code=404, detail="Precedent not found")

    await service.increment_usage("precedent", precedent_id)

    return PrecedentResponse(
        id=str(precedent.id),
        title=precedent.title,
        reference_code=precedent.reference_code,
        category=precedent.category.value,
        summary=precedent.summary,
        description=precedent.description,
        context=precedent.context,
        industry=precedent.industry,
        jurisdiction=precedent.jurisdiction,
        reporting_period=precedent.reporting_period,
        methods_used=precedent.methods_used,
        approach_description=precedent.approach_description,
        outcome=precedent.outcome,
        lessons_learned=precedent.lessons_learned,
        tags=precedent.tags,
        confidentiality_level=precedent.confidentiality_level,
        is_anonymized=precedent.is_anonymized,
        status=precedent.status.value,
        usage_count=precedent.usage_count,
        created_at=precedent.created_at.isoformat(),
    )


# ==================== Search Endpoints ====================

@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search knowledge base",
    description="Search across the knowledge base using semantic, full-text, or hybrid search.",
)
async def search_knowledge_base(
    request: SearchRequest,
    current_user: OptionalUser = None,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search the knowledge base."""
    service = KnowledgeBaseService(db)

    user_id = current_user.id if current_user else None

    if request.search_mode == SearchMode.SEMANTIC:
        results = await service.search(
            query=request.query,
            search_types=request.search_types,
            category=request.category,
            limit=request.limit,
            user_id=user_id,
        )
    elif request.search_mode == SearchMode.FULLTEXT:
        results = await service.search_fulltext(
            query=request.query,
            search_types=request.search_types,
            category=request.category,
            limit=request.limit,
            user_id=user_id,
        )
    else:  # hybrid (default)
        results = await service.search_hybrid(
            query=request.query,
            search_types=request.search_types,
            category=request.category,
            limit=request.limit,
            user_id=user_id,
        )

    search_results = [
        SearchResult(
            id=r["id"],
            type=r["type"],
            name=r.get("name"),
            title=r.get("title"),
            code=r.get("code"),
            reference_code=r.get("reference_code"),
            category=r["category"],
            summary=r["summary"],
            tags=r.get("tags"),
            similarity_score=r.get("similarity_score"),
            rank_score=r.get("rank_score"),
            combined_score=r.get("combined_score"),
        )
        for r in results
    ]

    return SearchResponse(
        query=request.query,
        search_mode=request.search_mode,
        result_count=len(search_results),
        results=search_results,
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search knowledge base (GET)",
    description="Search across the knowledge base using query parameters.",
)
async def search_knowledge_base_get(
    query: str = Query(..., min_length=1, max_length=1000),
    search_types: list[str] | None = Query(default=None),
    category: KnowledgeBaseCategory | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    search_mode: SearchMode = Query(default=SearchMode.HYBRID),
    current_user: OptionalUser = None,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search the knowledge base via GET request."""
    request = SearchRequest(
        query=query,
        search_types=search_types,
        category=category,
        limit=limit,
        search_mode=search_mode,
    )
    return await search_knowledge_base(request, current_user, db)


# ==================== Health Check ====================

@router.get(
    "/health",
    summary="Knowledge base health check",
    description="Check if the knowledge base service is operational.",
)
async def knowledge_base_health(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Check knowledge base health."""
    from sqlalchemy import text

    try:
        # Check if tables exist
        result = await db.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('actuarial_methods', 'templates', 'precedents')
        """))
        tables = [row[0] for row in result]

        # Check pgvector extension
        result = await db.execute(text("""
            SELECT extname FROM pg_extension WHERE extname = 'vector'
        """))
        pgvector_enabled = result.scalar_one_or_none() is not None

        return {
            "status": "healthy" if len(tables) == 3 else "degraded",
            "tables_found": tables,
            "pgvector_enabled": pgvector_enabled,
            "message": "Knowledge base operational" if len(tables) == 3 else "Some tables missing",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
