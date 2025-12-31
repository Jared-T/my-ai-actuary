"""
Workflow definition API routes.

Provides endpoints for:
- Creating, reading, updating, and deleting workflow definitions
- Validating workflow definitions
- Listing available workflow types
"""

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.exceptions import ValidationError
from models.workflow import WorkflowType
from services.workflow_definition import (
    WorkflowDefinition,
    WorkflowDefinitionService,
    WorkflowMetadata,
    InputsSchema,
    OutputsSchema,
    WorkflowStep,
    StepType,
    DataType,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


# ============================================================================
# Request/Response Models
# ============================================================================


class WorkflowTypeInfo(BaseModel):
    """Information about a workflow type."""

    type: str = Field(description="Workflow type identifier")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Description of the workflow type")


class WorkflowTypeListResponse(BaseModel):
    """Response for listing workflow types."""

    types: list[WorkflowTypeInfo] = Field(description="Available workflow types")


class StepTypeInfo(BaseModel):
    """Information about a step type."""

    type: str = Field(description="Step type identifier")
    description: str = Field(description="Description of the step type")


class StepTypeListResponse(BaseModel):
    """Response for listing step types."""

    types: list[StepTypeInfo] = Field(description="Available step types")


class DataTypeInfo(BaseModel):
    """Information about a data type."""

    type: str = Field(description="Data type identifier")
    description: str = Field(description="Description of the data type")


class DataTypeListResponse(BaseModel):
    """Response for listing data types."""

    types: list[DataTypeInfo] = Field(description="Available data types")


class WorkflowValidationResult(BaseModel):
    """Result of workflow validation."""

    valid: bool = Field(description="Whether the workflow is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class WorkflowCreateRequest(BaseModel):
    """Request to create a workflow definition."""

    name: str = Field(
        ...,
        description="Workflow name",
        min_length=1,
        max_length=200,
    )
    description: str = Field(
        default="",
        description="Workflow description",
    )
    workflow_type: WorkflowType = Field(
        ...,
        description="Type of workflow",
    )
    metadata: WorkflowMetadata | None = Field(
        default=None,
        description="Workflow metadata",
    )
    inputs: InputsSchema | None = Field(
        default=None,
        description="Input schema",
    )
    outputs: OutputsSchema | None = Field(
        default=None,
        description="Output schema",
    )
    steps: list[WorkflowStep] = Field(
        ...,
        description="Workflow steps",
        min_length=1,
    )
    timeout_seconds: int = Field(
        default=86400,
        description="Workflow timeout",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow variables",
    )


class WorkflowResponse(BaseModel):
    """Response containing a workflow definition."""

    id: str = Field(description="Workflow ID")
    name: str = Field(description="Workflow name")
    description: str = Field(description="Workflow description")
    workflow_type: str = Field(description="Workflow type")
    metadata: dict[str, Any] = Field(description="Workflow metadata")
    inputs: dict[str, Any] = Field(description="Input schema")
    outputs: dict[str, Any] = Field(description="Output schema")
    steps: list[dict[str, Any]] = Field(description="Workflow steps")
    timeout_seconds: int = Field(description="Timeout in seconds")
    variables: dict[str, Any] = Field(description="Workflow variables")

    @classmethod
    def from_definition(cls, workflow: WorkflowDefinition) -> "WorkflowResponse":
        """Create response from workflow definition."""
        data = workflow.model_dump(mode="json")
        return cls(**data)


class WorkflowYamlResponse(BaseModel):
    """Response containing workflow as YAML."""

    yaml: str = Field(description="Workflow definition as YAML")


class WorkflowJsonResponse(BaseModel):
    """Response containing workflow as JSON."""

    model_config = {"populate_by_name": True}

    json_content: str = Field(description="Workflow definition as JSON", serialization_alias="json")


class ExecutionOrderResponse(BaseModel):
    """Response containing workflow execution order."""

    levels: list[list[str]] = Field(
        description="Execution levels (steps in each level can run in parallel)"
    )


# ============================================================================
# Helper Functions
# ============================================================================


def _create_workflow_from_request(request: WorkflowCreateRequest) -> WorkflowDefinition:
    """
    Create a WorkflowDefinition from a WorkflowCreateRequest.

    This helper function centralizes the workflow creation logic to avoid
    code duplication across multiple API endpoints.

    Args:
        request: The workflow creation request

    Returns:
        A validated WorkflowDefinition instance
    """
    return WorkflowDefinition(
        name=request.name,
        description=request.description,
        workflow_type=request.workflow_type,
        metadata=request.metadata or WorkflowMetadata(),
        inputs=request.inputs or InputsSchema(),
        outputs=request.outputs or OutputsSchema(),
        steps=request.steps,
        timeout_seconds=request.timeout_seconds,
        variables=request.variables,
    )


# ============================================================================
# Workflow Type Descriptions
# ============================================================================

WORKFLOW_TYPE_DESCRIPTIONS: dict[WorkflowType, str] = {
    WorkflowType.DATA_INGESTION: "Ingest and load data from external sources",
    WorkflowType.DATA_VALIDATION: "Validate data quality and completeness",
    WorkflowType.DATA_TRANSFORMATION: "Transform and prepare data for analysis",
    WorkflowType.RESERVE_CALCULATION: "Calculate insurance reserves",
    WorkflowType.TRIANGLE_ANALYSIS: "Analyze claims development triangles",
    WorkflowType.IBNR_ESTIMATION: "Estimate incurred but not reported claims",
    WorkflowType.IFRS17_MEASUREMENT: "Perform IFRS17 measurement calculations",
    WorkflowType.CSM_CALCULATION: "Calculate Contractual Service Margin",
    WorkflowType.COHORT_GROUPING: "Group insurance contracts into cohorts",
    WorkflowType.ALM_ANALYSIS: "Asset-Liability Management analysis",
    WorkflowType.CASHFLOW_PROJECTION: "Project future cash flows",
    WorkflowType.DURATION_MATCHING: "Match asset and liability durations",
    WorkflowType.REINSURANCE_ANALYSIS: "Analyze reinsurance arrangements",
    WorkflowType.TREATY_CALCULATION: "Calculate reinsurance treaty amounts",
    WorkflowType.RECOVERIES_CALCULATION: "Calculate reinsurance recoveries",
    WorkflowType.REPORT_GENERATION: "Generate actuarial reports",
    WorkflowType.DASHBOARD_UPDATE: "Update dashboards with latest data",
    WorkflowType.QUALITY_CHECK: "Perform quality checks on outputs",
    WorkflowType.PEER_REVIEW: "Conduct peer review of work",
    WorkflowType.SIGN_OFF: "Final sign-off and approval",
    WorkflowType.CUSTOM: "Custom workflow type",
}

STEP_TYPE_DESCRIPTIONS: dict[StepType, str] = {
    StepType.AGENT: "Execute an AI agent to perform a task",
    StepType.TOOL: "Execute a specific tool or function",
    StepType.VALIDATION: "Validate data or outputs against rules",
    StepType.APPROVAL: "Wait for human approval before continuing",
    StepType.CONDITIONAL: "Branch based on a condition",
    StepType.PARALLEL: "Run multiple steps in parallel",
    StepType.LOOP: "Iterate over a collection of items",
    StepType.TRANSFORM: "Transform or aggregate data",
}

DATA_TYPE_DESCRIPTIONS: dict[DataType, str] = {
    DataType.STRING: "Text string value",
    DataType.INTEGER: "Whole number value",
    DataType.FLOAT: "Decimal number value",
    DataType.BOOLEAN: "True or false value",
    DataType.DATE: "Date value (YYYY-MM-DD)",
    DataType.DATETIME: "Date and time value (ISO 8601)",
    DataType.FILE: "File reference or path",
    DataType.DATAFRAME: "Tabular data (DataFrame)",
    DataType.JSON: "JSON object or array",
    DataType.ARRAY: "Array/list of values",
    DataType.OBJECT: "Nested object/dictionary",
}


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/types",
    response_model=WorkflowTypeListResponse,
    summary="List workflow types",
    description="Get a list of all available workflow types.",
)
async def list_workflow_types() -> WorkflowTypeListResponse:
    """List all available workflow types."""
    types = [
        WorkflowTypeInfo(
            type=wt.value,
            name=wt.value.replace("_", " ").title(),
            description=WORKFLOW_TYPE_DESCRIPTIONS.get(wt, ""),
        )
        for wt in WorkflowType
    ]
    return WorkflowTypeListResponse(types=types)


@router.get(
    "/step-types",
    response_model=StepTypeListResponse,
    summary="List step types",
    description="Get a list of all available workflow step types.",
)
async def list_step_types() -> StepTypeListResponse:
    """List all available step types."""
    types = [
        StepTypeInfo(
            type=st.value,
            description=STEP_TYPE_DESCRIPTIONS.get(st, ""),
        )
        for st in StepType
    ]
    return StepTypeListResponse(types=types)


@router.get(
    "/data-types",
    response_model=DataTypeListResponse,
    summary="List data types",
    description="Get a list of all available data types for workflow parameters.",
)
async def list_data_types() -> DataTypeListResponse:
    """List all available data types."""
    types = [
        DataTypeInfo(
            type=dt.value,
            description=DATA_TYPE_DESCRIPTIONS.get(dt, ""),
        )
        for dt in DataType
    ]
    return DataTypeListResponse(types=types)


@router.post(
    "/validate",
    response_model=WorkflowValidationResult,
    summary="Validate workflow definition",
    description="Validate a workflow definition and return any errors or warnings.",
)
async def validate_workflow(
    request: WorkflowCreateRequest,
) -> WorkflowValidationResult:
    """Validate a workflow definition."""
    service = WorkflowDefinitionService()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        workflow = _create_workflow_from_request(request)
        warnings = service.validate(workflow)
    except ValidationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Validation failed: {str(e)}")

    return WorkflowValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.post(
    "/validate/yaml",
    response_model=WorkflowValidationResult,
    summary="Validate YAML workflow definition",
    description="Validate a workflow definition from YAML content.",
)
async def validate_workflow_yaml(
    file: UploadFile = File(..., description="YAML workflow definition file"),
) -> WorkflowValidationResult:
    """Validate a workflow definition from YAML."""
    service = WorkflowDefinitionService()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        content = await file.read()
        yaml_content = content.decode("utf-8")
        workflow = service.parse_yaml(yaml_content)
        warnings = service.validate(workflow)
    except ValidationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Validation failed: {str(e)}")

    return WorkflowValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.post(
    "/validate/json",
    response_model=WorkflowValidationResult,
    summary="Validate JSON workflow definition",
    description="Validate a workflow definition from JSON content.",
)
async def validate_workflow_json(
    file: UploadFile = File(..., description="JSON workflow definition file"),
) -> WorkflowValidationResult:
    """Validate a workflow definition from JSON."""
    service = WorkflowDefinitionService()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        content = await file.read()
        json_content = content.decode("utf-8")
        workflow = service.parse_json(json_content)
        warnings = service.validate(workflow)
    except ValidationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Validation failed: {str(e)}")

    return WorkflowValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.post(
    "/create",
    response_model=WorkflowResponse,
    summary="Create workflow definition",
    description="Create a new workflow definition.",
)
async def create_workflow(
    request: WorkflowCreateRequest,
) -> WorkflowResponse:
    """Create a new workflow definition."""
    try:
        workflow = _create_workflow_from_request(request)
        return WorkflowResponse.from_definition(workflow)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create workflow: {str(e)}")


@router.post(
    "/parse/yaml",
    response_model=WorkflowResponse,
    summary="Parse YAML workflow",
    description="Parse a workflow definition from YAML content.",
)
async def parse_yaml_workflow(
    file: UploadFile = File(..., description="YAML workflow definition file"),
) -> WorkflowResponse:
    """Parse a workflow definition from YAML."""
    service = WorkflowDefinitionService()

    try:
        content = await file.read()
        yaml_content = content.decode("utf-8")
        workflow = service.parse_yaml(yaml_content)
        return WorkflowResponse.from_definition(workflow)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse YAML: {str(e)}")


@router.post(
    "/parse/json",
    response_model=WorkflowResponse,
    summary="Parse JSON workflow",
    description="Parse a workflow definition from JSON content.",
)
async def parse_json_workflow(
    file: UploadFile = File(..., description="JSON workflow definition file"),
) -> WorkflowResponse:
    """Parse a workflow definition from JSON."""
    service = WorkflowDefinitionService()

    try:
        content = await file.read()
        json_content = content.decode("utf-8")
        workflow = service.parse_json(json_content)
        return WorkflowResponse.from_definition(workflow)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON: {str(e)}")


@router.post(
    "/export/yaml",
    response_model=WorkflowYamlResponse,
    summary="Export workflow to YAML",
    description="Export a workflow definition to YAML format.",
)
async def export_workflow_yaml(
    request: WorkflowCreateRequest,
) -> WorkflowYamlResponse:
    """Export a workflow definition to YAML."""
    try:
        workflow = _create_workflow_from_request(request)
        return WorkflowYamlResponse(yaml=workflow.to_yaml())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to export workflow: {str(e)}")


@router.post(
    "/export/json",
    response_model=WorkflowJsonResponse,
    summary="Export workflow to JSON",
    description="Export a workflow definition to JSON format.",
)
async def export_workflow_json(
    request: WorkflowCreateRequest,
) -> WorkflowJsonResponse:
    """Export a workflow definition to JSON."""
    try:
        workflow = _create_workflow_from_request(request)
        return WorkflowJsonResponse(json_content=workflow.to_json())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to export workflow: {str(e)}")


@router.post(
    "/execution-order",
    response_model=ExecutionOrderResponse,
    summary="Get execution order",
    description="Get the execution order for a workflow (topological sort).",
)
async def get_execution_order(
    request: WorkflowCreateRequest,
) -> ExecutionOrderResponse:
    """Get the execution order for a workflow."""
    service = WorkflowDefinitionService()

    try:
        workflow = _create_workflow_from_request(request)
        levels = service.get_execution_order(workflow)
        return ExecutionOrderResponse(levels=levels)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get execution order: {str(e)}")
