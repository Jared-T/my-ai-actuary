"""
Tests for workflow definition service and schemas.

These tests verify:
- Workflow definition parsing (YAML and JSON)
- Workflow validation
- Step type configurations
- Execution order calculation
"""

import sys
from pathlib import Path

import pytest

# Import directly from the module to avoid issues with other services
# that have incompatible dependencies
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
spec = importlib.util.spec_from_file_location(
    'workflow_definition',
    Path(__file__).parent.parent / 'services' / 'workflow_definition.py'
)
wd_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd_module)

# Import all the classes from the workflow_definition module
WorkflowDefinition = wd_module.WorkflowDefinition
WorkflowDefinitionService = wd_module.WorkflowDefinitionService
WorkflowStep = wd_module.WorkflowStep
WorkflowMetadata = wd_module.WorkflowMetadata
InputsSchema = wd_module.InputsSchema
OutputsSchema = wd_module.OutputsSchema
ParameterSchema = wd_module.ParameterSchema
StepType = wd_module.StepType
DataType = wd_module.DataType
AgentStepConfig = wd_module.AgentStepConfig
ToolStepConfig = wd_module.ToolStepConfig
ValidationStepConfig = wd_module.ValidationStepConfig
ApprovalConfig = wd_module.ApprovalConfig
ApprovalType = wd_module.ApprovalType
StepCondition = wd_module.StepCondition
StepRetryConfig = wd_module.StepRetryConfig
RetryPolicy = wd_module.RetryPolicy
ErrorHandlingStrategy = wd_module.ErrorHandlingStrategy

from agent_definitions.config import AgentType
from models.workflow import WorkflowType
from core.exceptions import ValidationError


class TestParameterSchema:
    """Tests for ParameterSchema."""

    def test_create_string_parameter(self):
        """Test creating a string parameter."""
        param = ParameterSchema(
            name="test_param",
            type=DataType.STRING,
            description="A test parameter",
            required=True,
        )
        assert param.name == "test_param"
        assert param.type == DataType.STRING
        assert param.required is True

    def test_create_parameter_with_default(self):
        """Test creating a parameter with default value."""
        param = ParameterSchema(
            name="count",
            type=DataType.INTEGER,
            default=10,
            required=False,
        )
        assert param.default == 10
        assert param.required is False

    def test_parameter_name_validation(self):
        """Test that parameter names must be snake_case."""
        with pytest.raises(ValueError):
            ParameterSchema(
                name="Invalid-Name",  # Invalid: contains hyphen
                type=DataType.STRING,
            )

    def test_default_type_validation(self):
        """Test that default value type matches parameter type."""
        with pytest.raises(ValueError):
            ParameterSchema(
                name="count",
                type=DataType.INTEGER,
                default="not_an_integer",  # Invalid: string instead of int
            )


class TestWorkflowStep:
    """Tests for WorkflowStep."""

    def test_create_agent_step(self):
        """Test creating an agent step."""
        step = WorkflowStep(
            id="validate_data",
            name="Validate Input Data",
            type=StepType.AGENT,
            description="Validate the input data",
            agent=AgentStepConfig(
                agent_type=AgentType.DATA_QUALITY,
                prompt_template="Validate {{input.data_file}}",
            ),
        )
        assert step.id == "validate_data"
        assert step.type == StepType.AGENT
        assert step.agent is not None
        assert step.agent.agent_type == AgentType.DATA_QUALITY

    def test_create_tool_step(self):
        """Test creating a tool step."""
        step = WorkflowStep(
            id="load_file",
            name="Load Data File",
            type=StepType.TOOL,
            tool=ToolStepConfig(
                tool_name="load_data_file",
                parameters={"file_path": "{{input.data_file}}"},
            ),
        )
        assert step.type == StepType.TOOL
        assert step.tool is not None
        assert step.tool.tool_name == "load_data_file"

    def test_create_approval_step(self):
        """Test creating an approval step."""
        step = WorkflowStep(
            id="final_approval",
            name="Final Approval",
            type=StepType.APPROVAL,
            approval=ApprovalConfig(
                type=ApprovalType.REQUIRED,
                approvers=["chief_actuary"],
                deadline_hours=72,
            ),
        )
        assert step.type == StepType.APPROVAL
        assert step.approval is not None
        assert step.approval.type == ApprovalType.REQUIRED
        assert "chief_actuary" in step.approval.approvers

    def test_step_requires_matching_config(self):
        """Test that step type requires matching configuration."""
        with pytest.raises(ValueError):
            WorkflowStep(
                id="bad_step",
                name="Bad Step",
                type=StepType.AGENT,  # Agent type but no agent config
            )

    def test_step_id_validation(self):
        """Test that step IDs must be snake_case."""
        with pytest.raises(ValueError):
            WorkflowStep(
                id="Bad-Step-Id",  # Invalid: contains hyphen
                name="Bad Step",
                type=StepType.AGENT,
                agent=AgentStepConfig(
                    agent_type=AgentType.GENERAL,
                    prompt_template="Test",
                ),
            )


class TestWorkflowDefinition:
    """Tests for WorkflowDefinition."""

    def test_create_simple_workflow(self):
        """Test creating a simple workflow."""
        step = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Do something",
            ),
        )
        workflow = WorkflowDefinition(
            name="Simple Workflow",
            description="A simple test workflow",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )
        assert workflow.name == "Simple Workflow"
        assert len(workflow.steps) == 1
        assert workflow.id is not None

    def test_workflow_with_dependencies(self):
        """Test creating a workflow with step dependencies."""
        step1 = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 1",
            ),
        )
        step2 = WorkflowStep(
            id="step2",
            name="Second Step",
            type=StepType.AGENT,
            depends_on=["step1"],
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 2",
            ),
        )
        workflow = WorkflowDefinition(
            name="Dependent Workflow",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step1, step2],
        )
        assert len(workflow.steps) == 2
        assert "step1" in workflow.steps[1].depends_on

    def test_workflow_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        step1 = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            depends_on=["step2"],  # Depends on step2
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 1",
            ),
        )
        step2 = WorkflowStep(
            id="step2",
            name="Second Step",
            type=StepType.AGENT,
            depends_on=["step1"],  # Depends on step1 - circular!
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 2",
            ),
        )
        with pytest.raises(ValueError, match="Circular dependency"):
            WorkflowDefinition(
                name="Circular Workflow",
                workflow_type=WorkflowType.CUSTOM,
                steps=[step1, step2],
            )

    def test_workflow_unknown_dependency(self):
        """Test that unknown dependencies are detected."""
        step = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            depends_on=["nonexistent_step"],  # Unknown step
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 1",
            ),
        )
        with pytest.raises(ValueError, match="unknown step"):
            WorkflowDefinition(
                name="Bad Workflow",
                workflow_type=WorkflowType.CUSTOM,
                steps=[step],
            )

    def test_workflow_to_yaml(self):
        """Test YAML serialization."""
        step = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Do something",
            ),
        )
        workflow = WorkflowDefinition(
            name="Test Workflow",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )
        yaml_output = workflow.to_yaml()
        assert "name: Test Workflow" in yaml_output
        assert "workflow_type: custom" in yaml_output
        assert "step1" in yaml_output

    def test_workflow_to_json(self):
        """Test JSON serialization."""
        step = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Do something",
            ),
        )
        workflow = WorkflowDefinition(
            name="Test Workflow",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )
        json_output = workflow.to_json()
        assert '"name": "Test Workflow"' in json_output
        assert '"workflow_type": "custom"' in json_output

    def test_get_entry_steps(self):
        """Test getting entry steps (no dependencies)."""
        step1 = WorkflowStep(
            id="entry1",
            name="Entry 1",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Entry 1",
            ),
        )
        step2 = WorkflowStep(
            id="entry2",
            name="Entry 2",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Entry 2",
            ),
        )
        step3 = WorkflowStep(
            id="dependent",
            name="Dependent",
            type=StepType.AGENT,
            depends_on=["entry1", "entry2"],
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Dependent",
            ),
        )
        workflow = WorkflowDefinition(
            name="Test",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step1, step2, step3],
        )
        entry_steps = workflow.get_entry_steps()
        entry_ids = [s.id for s in entry_steps]
        assert "entry1" in entry_ids
        assert "entry2" in entry_ids
        assert "dependent" not in entry_ids


class TestWorkflowDefinitionService:
    """Tests for WorkflowDefinitionService."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return WorkflowDefinitionService()

    def test_parse_yaml(self, service):
        """Test parsing YAML content."""
        yaml_content = """
name: Test Workflow
workflow_type: custom
steps:
  - id: step1
    name: First Step
    type: agent
    agent:
      agent_type: general
      prompt_template: Do something
"""
        workflow = service.parse_yaml(yaml_content)
        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 1

    def test_parse_json(self, service):
        """Test parsing JSON content."""
        json_content = """
{
  "name": "Test Workflow",
  "workflow_type": "custom",
  "steps": [
    {
      "id": "step1",
      "name": "First Step",
      "type": "agent",
      "agent": {
        "agent_type": "general",
        "prompt_template": "Do something"
      }
    }
  ]
}
"""
        workflow = service.parse_json(json_content)
        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 1

    def test_parse_invalid_yaml(self, service):
        """Test that invalid YAML raises ValidationError."""
        invalid_yaml = "name: [invalid yaml structure"
        with pytest.raises(ValidationError):
            service.parse_yaml(invalid_yaml)

    def test_parse_invalid_json(self, service):
        """Test that invalid JSON raises ValidationError."""
        invalid_json = '{"name": "Test", invalid json}'
        with pytest.raises(ValidationError):
            service.parse_json(invalid_json)

    def test_validate_workflow(self, service):
        """Test workflow validation."""
        step = WorkflowStep(
            id="step1",
            name="First Step",
            type=StepType.AGENT,
            # No description - should trigger warning
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Do something",
            ),
        )
        workflow = WorkflowDefinition(
            name="Test",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )
        warnings = service.validate(workflow)
        assert len(warnings) > 0  # Should have warning about missing description

    def test_get_execution_order(self, service):
        """Test execution order calculation."""
        step1 = WorkflowStep(
            id="step1",
            name="Step 1",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 1",
            ),
        )
        step2 = WorkflowStep(
            id="step2",
            name="Step 2",
            type=StepType.AGENT,
            depends_on=["step1"],
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 2",
            ),
        )
        step3 = WorkflowStep(
            id="step3",
            name="Step 3",
            type=StepType.AGENT,
            depends_on=["step2"],
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Step 3",
            ),
        )
        workflow = WorkflowDefinition(
            name="Test",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step1, step2, step3],
        )
        levels = service.get_execution_order(workflow)
        assert len(levels) == 3
        assert "step1" in levels[0]
        assert "step2" in levels[1]
        assert "step3" in levels[2]

    def test_load_yaml_file(self, service, tmp_path):
        """Test loading a YAML file."""
        yaml_content = """
name: File Test Workflow
workflow_type: custom
steps:
  - id: step1
    name: First Step
    type: agent
    agent:
      agent_type: general
      prompt_template: Test
"""
        yaml_file = tmp_path / "test_workflow.yaml"
        yaml_file.write_text(yaml_content)

        workflow = service.load_from_file(yaml_file)
        assert workflow.name == "File Test Workflow"

    def test_load_json_file(self, service, tmp_path):
        """Test loading a JSON file."""
        json_content = """
{
  "name": "JSON File Test",
  "workflow_type": "custom",
  "steps": [
    {
      "id": "step1",
      "name": "First Step",
      "type": "agent",
      "agent": {
        "agent_type": "general",
        "prompt_template": "Test"
      }
    }
  ]
}
"""
        json_file = tmp_path / "test_workflow.json"
        json_file.write_text(json_content)

        workflow = service.load_from_file(json_file)
        assert workflow.name == "JSON File Test"

    def test_save_to_file_yaml(self, service, tmp_path):
        """Test saving workflow to YAML file."""
        step = WorkflowStep(
            id="step1",
            name="Step 1",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Test",
            ),
        )
        workflow = WorkflowDefinition(
            name="Save Test",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )

        output_file = tmp_path / "output.yaml"
        service.save_to_file(workflow, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Save Test" in content

    def test_save_to_file_json(self, service, tmp_path):
        """Test saving workflow to JSON file."""
        step = WorkflowStep(
            id="step1",
            name="Step 1",
            type=StepType.AGENT,
            agent=AgentStepConfig(
                agent_type=AgentType.GENERAL,
                prompt_template="Test",
            ),
        )
        workflow = WorkflowDefinition(
            name="Save Test",
            workflow_type=WorkflowType.CUSTOM,
            steps=[step],
        )

        output_file = tmp_path / "output.json"
        service.save_to_file(workflow, output_file, format="json")

        assert output_file.exists()
        content = output_file.read_text()
        assert '"Save Test"' in content


class TestExampleWorkflows:
    """Tests for example workflow files."""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return WorkflowDefinitionService()

    def test_load_reserve_calculation_workflow(self, service):
        """Test loading the reserve calculation example."""
        workflow_path = Path(__file__).parent.parent / "workflows" / "examples" / "reserve_calculation_workflow.yaml"
        if workflow_path.exists():
            workflow = service.load_from_file(workflow_path)
            assert workflow.name == "Quarterly Reserve Calculation"
            assert workflow.workflow_type == WorkflowType.RESERVE_CALCULATION
            assert len(workflow.steps) > 0

    def test_load_data_validation_workflow(self, service):
        """Test loading the data validation example."""
        workflow_path = Path(__file__).parent.parent / "workflows" / "examples" / "data_validation_workflow.json"
        if workflow_path.exists():
            workflow = service.load_from_file(workflow_path)
            assert workflow.name == "Data Quality Validation Workflow"
            assert workflow.workflow_type == WorkflowType.DATA_VALIDATION
            assert len(workflow.steps) > 0
