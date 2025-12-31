"""
Workflow definition service for actuarial multi-step processes.

This module provides Pydantic schemas and services for defining, validating,
and managing workflow definitions in YAML/JSON format. Workflow definitions
describe multi-step actuarial processes including inputs, agents, and outputs.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_definitions.config import AgentType
from core.exceptions import ValidationError
from core.logging import get_logger
from models.workflow import WorkflowType

logger = get_logger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Timeout constants (in seconds)
DEFAULT_STEP_TIMEOUT_SECONDS = 3600  # 1 hour
DEFAULT_WORKFLOW_TIMEOUT_SECONDS = 86400  # 24 hours
MAX_STEP_TIMEOUT_SECONDS = 86400  # 24 hours
MAX_WORKFLOW_TIMEOUT_SECONDS = 604800  # 7 days
MIN_WORKFLOW_TIMEOUT_SECONDS = 60  # 1 minute

# Retry constants
DEFAULT_MAX_RETRY_ATTEMPTS = 3
MAX_RETRY_ATTEMPTS = 10
DEFAULT_INITIAL_RETRY_DELAY_SECONDS = 5
DEFAULT_MAX_RETRY_DELAY_SECONDS = 300  # 5 minutes
MAX_RETRY_DELAY_SECONDS = 3600  # 1 hour

# Loop constants
DEFAULT_MAX_ITERATIONS = 1000
MAX_ITERATIONS = 10000


# ============================================================================
# Enums for workflow definition configuration
# ============================================================================


class StepType(str, Enum):
    """Types of workflow steps."""

    AGENT = "agent"  # Execute an agent
    TOOL = "tool"  # Execute a specific tool
    VALIDATION = "validation"  # Validate data or outputs
    APPROVAL = "approval"  # Wait for human approval
    CONDITIONAL = "conditional"  # Branch based on condition
    PARALLEL = "parallel"  # Run multiple steps in parallel
    LOOP = "loop"  # Iterate over items
    TRANSFORM = "transform"  # Transform/aggregate data


class DataType(str, Enum):
    """Supported data types for workflow inputs/outputs."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    FILE = "file"
    DATAFRAME = "dataframe"
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"


class ApprovalType(str, Enum):
    """Types of approval gates."""

    REQUIRED = "required"  # Always requires approval
    CONDITIONAL = "conditional"  # Requires approval based on condition
    OPTIONAL = "optional"  # Approval can be skipped


class RetryPolicy(str, Enum):
    """Retry policies for failed steps."""

    NONE = "none"  # No retry
    IMMEDIATE = "immediate"  # Retry immediately
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # Retry with exponential backoff
    LINEAR_BACKOFF = "linear_backoff"  # Retry with linear backoff


class ErrorHandlingStrategy(str, Enum):
    """Strategies for handling errors."""

    FAIL = "fail"  # Fail the entire workflow
    SKIP = "skip"  # Skip the step and continue
    RETRY = "retry"  # Retry the step
    FALLBACK = "fallback"  # Use fallback step/value


# ============================================================================
# Input/Output Schemas
# ============================================================================


class ParameterSchema(BaseModel):
    """Schema for a workflow parameter (input or output)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        description="Parameter name",
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    type: DataType = Field(
        ...,
        description="Data type of the parameter",
    )
    description: str = Field(
        default="",
        description="Human-readable description",
        max_length=500,
    )
    required: bool = Field(
        default=True,
        description="Whether the parameter is required",
    )
    default: Any = Field(
        default=None,
        description="Default value if not provided",
    )
    validation: dict[str, Any] | None = Field(
        default=None,
        description="Validation rules (min, max, pattern, enum, etc.)",
    )
    example: Any = Field(
        default=None,
        description="Example value for documentation",
    )

    @model_validator(mode="after")
    def validate_default_matches_type(self) -> "ParameterSchema":
        """Validate that default value matches the parameter type."""
        if self.default is None:
            return self
        # Basic type validation for default values
        type_validators = {
            DataType.STRING: lambda v: isinstance(v, str),
            DataType.INTEGER: lambda v: isinstance(v, int) and not isinstance(v, bool),
            DataType.FLOAT: lambda v: isinstance(v, (int, float)),
            DataType.BOOLEAN: lambda v: isinstance(v, bool),
            DataType.ARRAY: lambda v: isinstance(v, list),
            DataType.OBJECT: lambda v: isinstance(v, dict),
        }
        validator = type_validators.get(self.type)
        if validator and not validator(self.default):
            raise ValueError(
                f"Default value type does not match parameter type '{self.type}'"
            )
        return self


class InputsSchema(BaseModel):
    """Schema for workflow inputs."""

    model_config = ConfigDict(extra="forbid")

    parameters: list[ParameterSchema] = Field(
        default_factory=list,
        description="List of input parameters",
    )
    files: list[ParameterSchema] = Field(
        default_factory=list,
        description="List of required input files",
    )

    def get_parameter(self, name: str) -> ParameterSchema | None:
        """Get parameter by name."""
        for param in self.parameters:
            if param.name == name:
                return param
        return None


class OutputsSchema(BaseModel):
    """Schema for workflow outputs."""

    model_config = ConfigDict(extra="forbid")

    parameters: list[ParameterSchema] = Field(
        default_factory=list,
        description="List of output parameters",
    )
    artefacts: list[ParameterSchema] = Field(
        default_factory=list,
        description="List of artefacts to be generated",
    )


# ============================================================================
# Step Definitions
# ============================================================================


class StepCondition(BaseModel):
    """Condition for step execution or branching."""

    model_config = ConfigDict(extra="forbid")

    expression: str = Field(
        ...,
        description="Condition expression using step outputs (e.g., 'data_quality.score > 0.95')",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the condition",
    )


class StepRetryConfig(BaseModel):
    """Configuration for step retry behavior."""

    model_config = ConfigDict(extra="forbid")

    policy: RetryPolicy = Field(
        default=RetryPolicy.NONE,
        description="Retry policy to use",
    )
    max_attempts: int = Field(
        default=DEFAULT_MAX_RETRY_ATTEMPTS,
        ge=1,
        le=MAX_RETRY_ATTEMPTS,
        description="Maximum number of retry attempts",
    )
    initial_delay_seconds: int = Field(
        default=DEFAULT_INITIAL_RETRY_DELAY_SECONDS,
        ge=1,
        le=MAX_RETRY_DELAY_SECONDS,
        description="Initial delay before first retry",
    )
    max_delay_seconds: int = Field(
        default=DEFAULT_MAX_RETRY_DELAY_SECONDS,
        ge=1,
        le=MAX_RETRY_DELAY_SECONDS,
        description="Maximum delay between retries",
    )


class StepTimeout(BaseModel):
    """Timeout configuration for a step."""

    model_config = ConfigDict(extra="forbid")

    seconds: int = Field(
        default=DEFAULT_STEP_TIMEOUT_SECONDS,
        ge=1,
        le=MAX_STEP_TIMEOUT_SECONDS,
        description="Timeout in seconds",
    )
    action: Literal["fail", "skip", "notify"] = Field(
        default="fail",
        description="Action to take on timeout",
    )


class ApprovalConfig(BaseModel):
    """Configuration for approval gates."""

    model_config = ConfigDict(extra="forbid")

    type: ApprovalType = Field(
        default=ApprovalType.REQUIRED,
        description="Type of approval required",
    )
    approvers: list[str] = Field(
        default_factory=list,
        description="List of approver roles or user IDs",
    )
    condition: StepCondition | None = Field(
        default=None,
        description="Condition for conditional approval (only if type is CONDITIONAL)",
    )
    deadline_hours: int | None = Field(
        default=None,
        ge=1,
        le=720,
        description="Deadline for approval in hours",
    )
    auto_approve_on_deadline: bool = Field(
        default=False,
        description="Auto-approve if deadline passes",
    )
    message: str = Field(
        default="",
        description="Message to show to approvers",
    )


class AgentStepConfig(BaseModel):
    """Configuration for an agent step."""

    model_config = ConfigDict(extra="forbid")

    agent_type: AgentType = Field(
        ...,
        description="Type of agent to execute",
    )
    prompt_template: str = Field(
        ...,
        description="Prompt template with placeholders for inputs (e.g., '{{input.data_file}}')",
    )
    tools: list[str] = Field(
        default_factory=list,
        description="Specific tools to enable for this agent",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context to pass to the agent",
    )


class ToolStepConfig(BaseModel):
    """Configuration for a tool step."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(
        ...,
        description="Name of the tool to execute",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters to pass to the tool",
    )


class ValidationStepConfig(BaseModel):
    """Configuration for a validation step."""

    model_config = ConfigDict(extra="forbid")

    rules: list[dict[str, Any]] = Field(
        ...,
        description="Validation rules to apply",
    )
    fail_on_error: bool = Field(
        default=True,
        description="Whether to fail the workflow on validation error",
    )
    output_field: str = Field(
        default="validation_result",
        description="Name of the output field for validation results",
    )


class ConditionalBranch(BaseModel):
    """A branch in a conditional step."""

    model_config = ConfigDict(extra="forbid")

    condition: StepCondition = Field(
        ...,
        description="Condition for this branch",
    )
    steps: list[str] = Field(
        ...,
        description="Step IDs to execute if condition is true",
    )


class ConditionalStepConfig(BaseModel):
    """Configuration for a conditional step."""

    model_config = ConfigDict(extra="forbid")

    branches: list[ConditionalBranch] = Field(
        ...,
        description="List of conditional branches",
        min_length=1,
    )
    default_steps: list[str] = Field(
        default_factory=list,
        description="Default steps if no condition matches",
    )


class ParallelStepConfig(BaseModel):
    """Configuration for parallel step execution."""

    model_config = ConfigDict(extra="forbid")

    steps: list[str] = Field(
        ...,
        description="Step IDs to execute in parallel",
        min_length=2,
    )
    wait_for_all: bool = Field(
        default=True,
        description="Wait for all parallel steps to complete",
    )
    fail_fast: bool = Field(
        default=True,
        description="Fail immediately if any parallel step fails",
    )


class LoopStepConfig(BaseModel):
    """Configuration for a loop step."""

    model_config = ConfigDict(extra="forbid")

    items_expression: str = Field(
        ...,
        description="Expression to get items to iterate over",
    )
    item_variable: str = Field(
        default="item",
        description="Variable name for current item in loop",
    )
    steps: list[str] = Field(
        ...,
        description="Step IDs to execute for each item",
    )
    max_iterations: int = Field(
        default=DEFAULT_MAX_ITERATIONS,
        ge=1,
        le=MAX_ITERATIONS,
        description="Maximum number of iterations",
    )


class TransformStepConfig(BaseModel):
    """Configuration for a transform/aggregation step."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        ...,
        description="Source data expression",
    )
    transform: str = Field(
        ...,
        description="Transform type or expression",
    )
    output_field: str = Field(
        ...,
        description="Output field name for transformed data",
    )


class WorkflowStep(BaseModel):
    """Definition of a workflow step."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Unique identifier for the step",
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    name: str = Field(
        ...,
        description="Human-readable name for the step",
        min_length=1,
        max_length=200,
    )
    type: StepType = Field(
        ...,
        description="Type of step",
    )
    description: str = Field(
        default="",
        description="Detailed description of what this step does",
        max_length=1000,
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Step IDs this step depends on",
    )
    condition: StepCondition | None = Field(
        default=None,
        description="Condition for step execution",
    )
    retry: StepRetryConfig = Field(
        default_factory=StepRetryConfig,
        description="Retry configuration",
    )
    timeout: StepTimeout = Field(
        default_factory=StepTimeout,
        description="Timeout configuration",
    )
    error_handling: ErrorHandlingStrategy = Field(
        default=ErrorHandlingStrategy.FAIL,
        description="Error handling strategy",
    )
    approval: ApprovalConfig | None = Field(
        default=None,
        description="Approval gate configuration (only for approval steps)",
    )
    # Step type-specific configuration
    agent: AgentStepConfig | None = Field(
        default=None,
        description="Agent configuration (for agent steps)",
    )
    tool: ToolStepConfig | None = Field(
        default=None,
        description="Tool configuration (for tool steps)",
    )
    validation: ValidationStepConfig | None = Field(
        default=None,
        description="Validation configuration (for validation steps)",
    )
    conditional: ConditionalStepConfig | None = Field(
        default=None,
        description="Conditional configuration (for conditional steps)",
    )
    parallel: ParallelStepConfig | None = Field(
        default=None,
        description="Parallel configuration (for parallel steps)",
    )
    loop: LoopStepConfig | None = Field(
        default=None,
        description="Loop configuration (for loop steps)",
    )
    transform: TransformStepConfig | None = Field(
        default=None,
        description="Transform configuration (for transform steps)",
    )
    outputs: list[ParameterSchema] = Field(
        default_factory=list,
        description="Output parameters produced by this step",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the step",
    )

    @model_validator(mode="after")
    def validate_step_config(self) -> "WorkflowStep":
        """Validate that step has the correct configuration for its type."""
        type_config_map = {
            StepType.AGENT: "agent",
            StepType.TOOL: "tool",
            StepType.VALIDATION: "validation",
            StepType.CONDITIONAL: "conditional",
            StepType.PARALLEL: "parallel",
            StepType.LOOP: "loop",
            StepType.TRANSFORM: "transform",
            StepType.APPROVAL: None,  # Uses approval field
        }

        expected_config = type_config_map.get(self.type)
        if expected_config and getattr(self, expected_config) is None:
            raise ValueError(
                f"Step type '{self.type}' requires '{expected_config}' configuration"
            )

        # Validation for approval step
        if self.type == StepType.APPROVAL and self.approval is None:
            raise ValueError("Approval step requires 'approval' configuration")

        return self


# ============================================================================
# Main Workflow Definition
# ============================================================================


class WorkflowMetadata(BaseModel):
    """Metadata about the workflow definition."""

    model_config = ConfigDict(extra="forbid")

    author: str = Field(
        default="",
        description="Author of the workflow definition",
    )
    version: str = Field(
        default="1.0.0",
        description="Version of the workflow definition",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization",
    )
    documentation_url: str | None = Field(
        default=None,
        description="URL to workflow documentation",
    )


class WorkflowDefinition(BaseModel):
    """
    Complete workflow definition for actuarial multi-step processes.

    This is the top-level schema for YAML/JSON workflow definitions.
    """

    model_config = ConfigDict(extra="forbid")

    # Identification
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique workflow identifier",
    )
    name: str = Field(
        ...,
        description="Workflow name",
        min_length=1,
        max_length=200,
    )
    description: str = Field(
        default="",
        description="Detailed workflow description",
        max_length=2000,
    )
    workflow_type: WorkflowType = Field(
        ...,
        description="Type of actuarial workflow",
    )

    # Metadata
    metadata: WorkflowMetadata = Field(
        default_factory=WorkflowMetadata,
        description="Workflow metadata",
    )

    # Inputs and Outputs
    inputs: InputsSchema = Field(
        default_factory=InputsSchema,
        description="Workflow input schema",
    )
    outputs: OutputsSchema = Field(
        default_factory=OutputsSchema,
        description="Workflow output schema",
    )

    # Steps
    steps: list[WorkflowStep] = Field(
        ...,
        description="Workflow steps to execute",
        min_length=1,
    )

    # Global configuration
    timeout_seconds: int = Field(
        default=DEFAULT_WORKFLOW_TIMEOUT_SECONDS,
        ge=MIN_WORKFLOW_TIMEOUT_SECONDS,
        le=MAX_WORKFLOW_TIMEOUT_SECONDS,
        description="Global workflow timeout in seconds (default: 24 hours)",
    )
    retry: StepRetryConfig = Field(
        default_factory=StepRetryConfig,
        description="Default retry configuration for steps",
    )
    error_handling: ErrorHandlingStrategy = Field(
        default=ErrorHandlingStrategy.FAIL,
        description="Default error handling strategy",
    )

    # Variables
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-level variables",
    )

    @model_validator(mode="after")
    def validate_workflow(self) -> "WorkflowDefinition":
        """Validate the complete workflow definition."""
        step_ids = {step.id for step in self.steps}

        # Validate step dependencies exist
        for step in self.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ValueError(
                        f"Step '{step.id}' depends on unknown step '{dep_id}'"
                    )

        # Validate no circular dependencies
        self._check_circular_dependencies()

        # Validate parallel/conditional/loop step references
        for step in self.steps:
            if step.parallel:
                for ref_id in step.parallel.steps:
                    if ref_id not in step_ids:
                        raise ValueError(
                            f"Parallel step '{step.id}' references unknown step '{ref_id}'"
                        )
            if step.conditional:
                for branch in step.conditional.branches:
                    for ref_id in branch.steps:
                        if ref_id not in step_ids:
                            raise ValueError(
                                f"Conditional step '{step.id}' references unknown step '{ref_id}'"
                            )
                for ref_id in step.conditional.default_steps:
                    if ref_id not in step_ids:
                        raise ValueError(
                            f"Conditional step '{step.id}' references unknown step '{ref_id}'"
                        )
            if step.loop:
                for ref_id in step.loop.steps:
                    if ref_id not in step_ids:
                        raise ValueError(
                            f"Loop step '{step.id}' references unknown step '{ref_id}'"
                        )

        return self

    def _check_circular_dependencies(self) -> None:
        """Check for circular dependencies in step graph."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            step = self.get_step(step_id)
            if step:
                for dep_id in step.depends_on:
                    if dep_id not in visited:
                        if dfs(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True

            rec_stack.remove(step_id)
            return False

        for step in self.steps:
            if step.id not in visited:
                if dfs(step.id):
                    raise ValueError("Circular dependency detected in workflow steps")

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Get a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def get_entry_steps(self) -> list[WorkflowStep]:
        """Get steps with no dependencies (entry points)."""
        return [step for step in self.steps if not step.depends_on]

    def get_dependent_steps(self, step_id: str) -> list[WorkflowStep]:
        """Get steps that depend on a given step."""
        return [step for step in self.steps if step_id in step.depends_on]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(mode="json")

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        return yaml.dump(
            self.model_dump(mode="json"),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.model_dump_json(indent=2)


# ============================================================================
# Workflow Definition Service
# ============================================================================


class WorkflowDefinitionService:
    """
    Service for managing workflow definitions.

    Provides methods for parsing, validating, loading, and saving
    workflow definitions in YAML and JSON formats.
    """

    def __init__(self) -> None:
        """Initialize the workflow definition service."""
        self.logger = get_logger(__name__)

    def parse_yaml(self, yaml_content: str) -> WorkflowDefinition:
        """
        Parse a YAML string into a WorkflowDefinition.

        Args:
            yaml_content: YAML string to parse

        Returns:
            Validated WorkflowDefinition

        Raises:
            ValidationError: If the YAML is invalid
        """
        try:
            data = yaml.safe_load(yaml_content)
            if data is None:
                raise ValidationError("Empty YAML content")
            return WorkflowDefinition.model_validate(data)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML syntax: {e}")
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Failed to parse workflow definition: {e}")

    def parse_json(self, json_content: str) -> WorkflowDefinition:
        """
        Parse a JSON string into a WorkflowDefinition.

        Args:
            json_content: JSON string to parse

        Returns:
            Validated WorkflowDefinition

        Raises:
            ValidationError: If the JSON is invalid
        """
        try:
            return WorkflowDefinition.model_validate_json(json_content)
        except Exception as e:
            raise ValidationError(f"Failed to parse workflow definition: {e}")

    def load_from_file(self, file_path: str | Path) -> WorkflowDefinition:
        """
        Load a workflow definition from a file.

        Args:
            file_path: Path to YAML or JSON file

        Returns:
            Validated WorkflowDefinition

        Raises:
            ValidationError: If the file cannot be loaded or parsed
            FileNotFoundError: If the file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")

        content = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return self.parse_yaml(content)
        elif suffix == ".json":
            return self.parse_json(content)
        else:
            raise ValidationError(
                f"Unsupported file format: {suffix}. Use .yaml, .yml, or .json"
            )

    def save_to_file(
        self,
        workflow: WorkflowDefinition,
        file_path: str | Path,
        format: Literal["yaml", "json"] | None = None,
    ) -> None:
        """
        Save a workflow definition to a file.

        Args:
            workflow: The workflow definition to save
            file_path: Path to save to
            format: Output format (auto-detected from extension if not provided)
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if format is None:
            suffix = path.suffix.lower()
            if suffix in (".yaml", ".yml"):
                format = "yaml"
            elif suffix == ".json":
                format = "json"
            else:
                format = "yaml"  # Default to YAML

        if format == "yaml":
            content = workflow.to_yaml()
        else:
            content = workflow.to_json()

        path.write_text(content, encoding="utf-8")
        self.logger.info("Saved workflow definition", path=str(path), format=format)

    def validate(self, workflow: WorkflowDefinition) -> list[str]:
        """
        Validate a workflow definition and return any warnings.

        Args:
            workflow: The workflow definition to validate

        Returns:
            List of warning messages (empty if no warnings)
        """
        warnings: list[str] = []

        # Check for unreferenced steps (potential dead code)
        referenced_steps: set[str] = set()
        for step in workflow.steps:
            referenced_steps.update(step.depends_on)
            if step.parallel:
                referenced_steps.update(step.parallel.steps)
            if step.conditional:
                for branch in step.conditional.branches:
                    referenced_steps.update(branch.steps)
                referenced_steps.update(step.conditional.default_steps)
            if step.loop:
                referenced_steps.update(step.loop.steps)

        all_step_ids = {step.id for step in workflow.steps}
        entry_steps = {step.id for step in workflow.get_entry_steps()}
        unreferenced = all_step_ids - referenced_steps - entry_steps

        if unreferenced:
            warnings.append(
                f"Steps not referenced by any other step: {', '.join(unreferenced)}"
            )

        # Check for missing descriptions
        steps_without_desc = [step.id for step in workflow.steps if not step.description]
        if steps_without_desc:
            warnings.append(
                f"Steps without descriptions: {', '.join(steps_without_desc)}"
            )

        # Check for approval steps without approvers
        for step in workflow.steps:
            if step.type == StepType.APPROVAL and step.approval:
                if not step.approval.approvers:
                    warnings.append(f"Approval step '{step.id}' has no approvers defined")

        return warnings

    def get_execution_order(self, workflow: WorkflowDefinition) -> list[list[str]]:
        """
        Get the execution order of steps (topological sort).

        Returns a list of levels, where each level contains steps
        that can be executed in parallel.

        Args:
            workflow: The workflow definition

        Returns:
            List of step ID groups (execution levels)
        """
        in_degree: dict[str, int] = {step.id: len(step.depends_on) for step in workflow.steps}
        levels: list[list[str]] = []

        while True:
            # Find all steps with no remaining dependencies
            ready = [step_id for step_id, degree in in_degree.items() if degree == 0]
            if not ready:
                break

            levels.append(ready)

            # Remove these steps and update dependencies
            for step_id in ready:
                del in_degree[step_id]
                for dependent in workflow.get_dependent_steps(step_id):
                    if dependent.id in in_degree:
                        in_degree[dependent.id] -= 1

        return levels


# ============================================================================
# Convenience Functions
# ============================================================================


def load_workflow(file_path: str | Path) -> WorkflowDefinition:
    """
    Load a workflow definition from a file.

    Convenience function that uses WorkflowDefinitionService.

    Args:
        file_path: Path to YAML or JSON file

    Returns:
        Validated WorkflowDefinition
    """
    service = WorkflowDefinitionService()
    return service.load_from_file(file_path)


def parse_workflow_yaml(yaml_content: str) -> WorkflowDefinition:
    """
    Parse a YAML string into a WorkflowDefinition.

    Convenience function that uses WorkflowDefinitionService.

    Args:
        yaml_content: YAML string to parse

    Returns:
        Validated WorkflowDefinition
    """
    service = WorkflowDefinitionService()
    return service.parse_yaml(yaml_content)


def parse_workflow_json(json_content: str) -> WorkflowDefinition:
    """
    Parse a JSON string into a WorkflowDefinition.

    Convenience function that uses WorkflowDefinitionService.

    Args:
        json_content: JSON string to parse

    Returns:
        Validated WorkflowDefinition
    """
    service = WorkflowDefinitionService()
    return service.parse_json(json_content)


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Constants
    "DEFAULT_STEP_TIMEOUT_SECONDS",
    "DEFAULT_WORKFLOW_TIMEOUT_SECONDS",
    "MAX_STEP_TIMEOUT_SECONDS",
    "MAX_WORKFLOW_TIMEOUT_SECONDS",
    "MIN_WORKFLOW_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RETRY_ATTEMPTS",
    "MAX_RETRY_ATTEMPTS",
    "DEFAULT_INITIAL_RETRY_DELAY_SECONDS",
    "DEFAULT_MAX_RETRY_DELAY_SECONDS",
    "MAX_RETRY_DELAY_SECONDS",
    "DEFAULT_MAX_ITERATIONS",
    "MAX_ITERATIONS",
    # Enums
    "StepType",
    "DataType",
    "ApprovalType",
    "RetryPolicy",
    "ErrorHandlingStrategy",
    # Schema classes
    "ParameterSchema",
    "InputsSchema",
    "OutputsSchema",
    "StepCondition",
    "StepRetryConfig",
    "StepTimeout",
    "ApprovalConfig",
    "AgentStepConfig",
    "ToolStepConfig",
    "ValidationStepConfig",
    "ConditionalBranch",
    "ConditionalStepConfig",
    "ParallelStepConfig",
    "LoopStepConfig",
    "TransformStepConfig",
    "WorkflowStep",
    "WorkflowMetadata",
    "WorkflowDefinition",
    # Service
    "WorkflowDefinitionService",
    # Convenience functions
    "load_workflow",
    "parse_workflow_yaml",
    "parse_workflow_json",
]
