"""
Knowledge base function tools for agents using OpenAI Agents SDK.

Provides tools for agents to search and retrieve information from the
actuarial methods library, templates, and precedents.
"""

from typing import Any
from uuid import UUID

from agents import function_tool

from core.database import get_db_context
from core.logging import get_logger
from models.knowledge_base import KnowledgeBaseCategory
from services.knowledge_base_service import KnowledgeBaseService

logger = get_logger(__name__)


@function_tool
async def search_knowledge_base(
    query: str,
    search_types: list[str] | None = None,
    category: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Search the actuarial knowledge base for methods, templates, and precedents.

    Use this tool to find relevant actuarial methods, document templates, or
    historical precedents based on a natural language query. The search uses
    semantic similarity to find the most relevant results.

    Args:
        query: Natural language search query describing what you're looking for.
               Example: "IBNR estimation methods for long-tail liability"
        search_types: Optional list of types to search. Valid values:
                     - "method": Actuarial methods and techniques
                     - "template": Document templates and report structures
                     - "precedent": Historical cases and examples
                     If not specified, searches all types.
        category: Optional category filter. Valid values:
                 - "reserving": Reserving methods and techniques
                 - "ifrs17": IFRS 17 related content
                 - "alm": Asset-Liability Management
                 - "reinsurance": Reinsurance analysis
                 - "pricing": Pricing methods
                 - "valuation": Valuation techniques
                 - "data_quality": Data quality and validation
                 - "reporting": Reporting and disclosure
        limit: Maximum number of results to return (default: 5, max: 20)

    Returns:
        Dictionary containing:
        - query: The search query used
        - result_count: Number of results found
        - results: List of matching items with:
            - id: Unique identifier
            - type: "method", "template", or "precedent"
            - name/title: Item name or title
            - summary: Brief description
            - category: Content category
            - similarity_score: Relevance score (0-1)
    """
    # Validate and parse inputs
    limit = min(max(1, limit), 20)

    kb_category = None
    if category:
        try:
            kb_category = KnowledgeBaseCategory(category)
        except ValueError:
            return {
                "error": f"Invalid category: {category}",
                "valid_categories": [c.value for c in KnowledgeBaseCategory],
            }

    valid_types = {"method", "template", "precedent"}
    if search_types:
        invalid_types = set(search_types) - valid_types
        if invalid_types:
            return {
                "error": f"Invalid search types: {invalid_types}",
                "valid_types": list(valid_types),
            }

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)
            results = await service.search_hybrid(
                query=query,
                search_types=search_types,
                category=kb_category,
                limit=limit,
            )

            # Format results for agent consumption
            formatted_results = []
            for r in results:
                formatted = {
                    "id": r["id"],
                    "type": r["type"],
                    "category": r["category"],
                    "summary": r["summary"],
                    "similarity_score": round(r.get("combined_score", r.get("similarity_score", 0)), 3),
                }

                # Add type-specific fields
                if r["type"] == "method":
                    formatted["name"] = r.get("name")
                    formatted["code"] = r.get("code")
                elif r["type"] == "template":
                    formatted["name"] = r.get("name")
                    formatted["code"] = r.get("code")
                    formatted["output_format"] = r.get("output_format")
                elif r["type"] == "precedent":
                    formatted["title"] = r.get("title")
                    formatted["reference_code"] = r.get("reference_code")
                    formatted["industry"] = r.get("industry")
                    formatted["methods_used"] = r.get("methods_used")

                if r.get("tags"):
                    formatted["tags"] = r["tags"]

                formatted_results.append(formatted)

            logger.info(
                "Knowledge base search completed",
                query=query[:100],
                result_count=len(formatted_results),
            )

            return {
                "query": query,
                "result_count": len(formatted_results),
                "results": formatted_results,
            }

    except Exception as e:
        logger.error("Knowledge base search failed", error=str(e))
        return {
            "error": f"Search failed: {str(e)}",
            "query": query,
        }


@function_tool
async def get_actuarial_method(
    method_code: str | None = None,
    method_id: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve detailed information about a specific actuarial method.

    Use this tool when you need comprehensive details about a particular
    actuarial method, including its description, use cases, mathematical
    formulation, and implementation guidance.

    Args:
        method_code: The short code for the method (e.g., "CHAIN_LADDER", "BF").
                    Preferred over method_id for readability.
        method_id: The UUID of the method. Use if you have the ID from a search.

    Returns:
        Dictionary containing full method details:
        - id: Unique identifier
        - name: Method name
        - code: Short code
        - category: Method category
        - summary: Brief summary
        - description: Detailed description
        - use_cases: Typical use cases
        - mathematical_formulation: Mathematical formulas (if available)
        - implementation_guidance: Step-by-step guidance
        - limitations: Known limitations
        - related_standards: Related regulatory standards
        - tags: Associated tags
    """
    if not method_code and not method_id:
        return {"error": "Either method_code or method_id must be provided"}

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)

            if method_code:
                method = await service.get_method_by_code(method_code)
            else:
                method = await service.get_method(UUID(method_id))

            if not method:
                return {
                    "error": "Method not found",
                    "method_code": method_code,
                    "method_id": method_id,
                }

            # Increment usage count
            await service.increment_usage("method", method.id)

            return {
                "id": str(method.id),
                "name": method.name,
                "code": method.code,
                "category": method.category.value,
                "summary": method.summary,
                "description": method.description,
                "use_cases": method.use_cases,
                "mathematical_formulation": method.mathematical_formulation,
                "implementation_guidance": method.implementation_guidance,
                "limitations": method.limitations,
                "related_standards": method.related_standards,
                "tags": method.tags,
                "version": method.version,
            }

    except Exception as e:
        logger.error("Failed to get actuarial method", error=str(e))
        return {"error": f"Failed to retrieve method: {str(e)}"}


@function_tool
async def get_template(
    template_code: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve detailed information about a specific document template.

    Use this tool when you need details about a template for generating
    actuarial reports or documents.

    Args:
        template_code: The short code for the template.
        template_id: The UUID of the template.

    Returns:
        Dictionary containing full template details:
        - id: Unique identifier
        - name: Template name
        - code: Short code
        - template_type: Type of template
        - category: Content category
        - summary: Brief description
        - description: Detailed description
        - structure: Template structure definition
        - required_inputs: Required data inputs
        - output_format: Output format (word, pdf, etc.)
        - tags: Associated tags
    """
    if not template_code and not template_id:
        return {"error": "Either template_code or template_id must be provided"}

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)

            if template_code:
                template = await service.get_template_by_code(template_code)
            else:
                template = await service.get_template(UUID(template_id))

            if not template:
                return {
                    "error": "Template not found",
                    "template_code": template_code,
                    "template_id": template_id,
                }

            await service.increment_usage("template", template.id)

            return {
                "id": str(template.id),
                "name": template.name,
                "code": template.code,
                "template_type": template.template_type.value,
                "category": template.category.value,
                "summary": template.summary,
                "description": template.description,
                "structure": template.structure,
                "required_inputs": template.required_inputs,
                "output_format": template.output_format,
                "tags": template.tags,
                "version": template.version,
            }

    except Exception as e:
        logger.error("Failed to get template", error=str(e))
        return {"error": f"Failed to retrieve template: {str(e)}"}


@function_tool
async def get_precedent(
    reference_code: str | None = None,
    precedent_id: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve detailed information about a historical precedent case.

    Use this tool when you need details about a past actuarial case,
    including the approach taken, methods used, and lessons learned.

    Args:
        reference_code: The unique reference code for the precedent.
        precedent_id: The UUID of the precedent.

    Returns:
        Dictionary containing full precedent details:
        - id: Unique identifier
        - title: Case title
        - reference_code: Unique reference code
        - category: Content category
        - summary: Brief summary
        - description: Detailed case description
        - context: Business context
        - industry: Industry sector
        - jurisdiction: Regulatory jurisdiction
        - reporting_period: Reporting period
        - methods_used: Actuarial methods applied
        - approach_description: Approach taken
        - outcome: Results and outcomes
        - lessons_learned: Key lessons
        - tags: Associated tags
    """
    if not reference_code and not precedent_id:
        return {"error": "Either reference_code or precedent_id must be provided"}

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)

            if reference_code:
                precedent = await service.get_precedent_by_reference(reference_code)
            else:
                precedent = await service.get_precedent(UUID(precedent_id))

            if not precedent:
                return {
                    "error": "Precedent not found",
                    "reference_code": reference_code,
                    "precedent_id": precedent_id,
                }

            await service.increment_usage("precedent", precedent.id)

            return {
                "id": str(precedent.id),
                "title": precedent.title,
                "reference_code": precedent.reference_code,
                "category": precedent.category.value,
                "summary": precedent.summary,
                "description": precedent.description,
                "context": precedent.context,
                "industry": precedent.industry,
                "jurisdiction": precedent.jurisdiction,
                "reporting_period": precedent.reporting_period,
                "methods_used": precedent.methods_used,
                "approach_description": precedent.approach_description,
                "outcome": precedent.outcome,
                "lessons_learned": precedent.lessons_learned,
                "tags": precedent.tags,
                "confidentiality_level": precedent.confidentiality_level,
            }

    except Exception as e:
        logger.error("Failed to get precedent", error=str(e))
        return {"error": f"Failed to retrieve precedent: {str(e)}"}


@function_tool
async def list_methods_by_category(
    category: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    List all actuarial methods in a specific category.

    Use this tool to discover available methods within a category,
    such as all reserving methods or all IFRS 17 methods.

    Args:
        category: The category to list methods for. Valid values:
                 - "reserving": Reserving methods
                 - "ifrs17": IFRS 17 methods
                 - "alm": ALM methods
                 - "reinsurance": Reinsurance methods
                 - "pricing": Pricing methods
                 - "valuation": Valuation methods
        limit: Maximum number of methods to return (default: 10, max: 50)

    Returns:
        Dictionary containing:
        - category: The category queried
        - count: Number of methods found
        - methods: List of methods with basic info
    """
    try:
        kb_category = KnowledgeBaseCategory(category)
    except ValueError:
        return {
            "error": f"Invalid category: {category}",
            "valid_categories": [c.value for c in KnowledgeBaseCategory],
        }

    limit = min(max(1, limit), 50)

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)
            methods = await service.list_methods(
                category=kb_category,
                limit=limit,
            )

            return {
                "category": category,
                "count": len(methods),
                "methods": [
                    {
                        "id": str(m.id),
                        "name": m.name,
                        "code": m.code,
                        "summary": m.summary,
                        "tags": m.tags,
                        "usage_count": m.usage_count,
                    }
                    for m in methods
                ],
            }

    except Exception as e:
        logger.error("Failed to list methods", error=str(e))
        return {"error": f"Failed to list methods: {str(e)}"}


@function_tool
async def find_similar_precedents(
    description: str,
    industry: str | None = None,
    methods_used: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Find historical precedents similar to a given situation.

    Use this tool when you need to find past cases that are similar
    to a current engagement or analysis situation.

    Args:
        description: Description of the current situation or analysis needed.
                    Example: "Reserve adequacy analysis for motor third party liability"
        industry: Optional industry filter (e.g., "Life Insurance", "P&C", "Health")
        methods_used: Optional list of methods to filter by
        limit: Maximum number of precedents to return (default: 5, max: 20)

    Returns:
        Dictionary containing:
        - description: The situation described
        - count: Number of similar precedents found
        - precedents: List of similar cases with relevance scores
    """
    limit = min(max(1, limit), 20)

    try:
        async with get_db_context() as db:
            service = KnowledgeBaseService(db)

            # Use semantic search to find similar precedents
            results = await service.search(
                query=description,
                search_types=["precedent"],
                limit=limit * 2,  # Get more for filtering
            )

            # Filter by industry and methods if specified
            filtered = []
            for r in results:
                if industry and r.get("industry") != industry:
                    continue
                if methods_used:
                    r_methods = r.get("methods_used") or []
                    if not any(m in r_methods for m in methods_used):
                        continue
                filtered.append(r)

            filtered = filtered[:limit]

            return {
                "description": description[:200],
                "filters": {
                    "industry": industry,
                    "methods_used": methods_used,
                },
                "count": len(filtered),
                "precedents": [
                    {
                        "id": p["id"],
                        "title": p.get("title"),
                        "reference_code": p.get("reference_code"),
                        "summary": p["summary"],
                        "industry": p.get("industry"),
                        "methods_used": p.get("methods_used"),
                        "similarity_score": round(p.get("similarity_score", 0), 3),
                    }
                    for p in filtered
                ],
            }

    except Exception as e:
        logger.error("Failed to find similar precedents", error=str(e))
        return {"error": f"Failed to find precedents: {str(e)}"}


# Export all tools for easy import
KNOWLEDGE_BASE_TOOLS = [
    search_knowledge_base,
    get_actuarial_method,
    get_template,
    get_precedent,
    list_methods_by_category,
    find_similar_precedents,
]
