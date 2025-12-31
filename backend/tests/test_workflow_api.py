"""
Tests for workflow definition API routes.

These tests verify the FastAPI routes work correctly by testing
them with TestClient.
"""

import sys
from pathlib import Path

import pytest

# Insert backend path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test the API routes work by testing them as unit tests
# without starting the full server (to avoid the tools issue)
from api.routes.workflows import (
    list_workflow_types,
    list_step_types,
    list_data_types,
    validate_workflow,
    create_workflow,
    export_workflow_yaml,
    get_execution_order,
    WORKFLOW_TYPE_DESCRIPTIONS,
    STEP_TYPE_DESCRIPTIONS,
    DATA_TYPE_DESCRIPTIONS,
    WorkflowCreateRequest,
    WorkflowValidationResult,
    WorkflowResponse,
    WorkflowYamlResponse,
    ExecutionOrderResponse,
    WorkflowStep,  # Import from the same module as API uses
)


class TestWorkflowTypesEndpoint:
    """Tests for /workflows/types endpoint."""

    @pytest.mark.asyncio
    async def test_list_workflow_types(self):
        """Test listing workflow types."""
        response = await list_workflow_types()

        assert hasattr(response, 'types')
        assert len(response.types) > 0

        # Check first type has expected structure
        first_type = response.types[0]
        assert hasattr(first_type, 'type')
        assert hasattr(first_type, 'name')
        assert hasattr(first_type, 'description')

    @pytest.mark.asyncio
    async def test_workflow_type_descriptions_exist(self):
        """Test that all workflow types have descriptions."""
        from models.workflow import WorkflowType

        for wt in WorkflowType:
            assert wt in WORKFLOW_TYPE_DESCRIPTIONS


class TestStepTypesEndpoint:
    """Tests for /workflows/step-types endpoint."""

    @pytest.mark.asyncio
    async def test_list_step_types(self):
        """Test listing step types."""
        response = await list_step_types()

        assert hasattr(response, 'types')
        assert len(response.types) > 0

        # Check for expected step types
        type_ids = [t.type for t in response.types]
        assert 'agent' in type_ids
        assert 'tool' in type_ids
        assert 'approval' in type_ids


class TestDataTypesEndpoint:
    """Tests for /workflows/data-types endpoint."""

    @pytest.mark.asyncio
    async def test_list_data_types(self):
        """Test listing data types."""
        response = await list_data_types()

        assert hasattr(response, 'types')
        assert len(response.types) > 0

        # Check for expected data types
        type_ids = [t.type for t in response.types]
        assert 'string' in type_ids
        assert 'integer' in type_ids
        assert 'float' in type_ids


class TestValidateEndpoint:
    """Tests for /workflows/validate endpoint."""

    @pytest.mark.asyncio
    async def test_validate_valid_workflow(self):
        """Test validating a valid workflow."""
        request = WorkflowCreateRequest(
            name="Test Workflow",
            description="A test workflow",
            workflow_type="custom",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="First Step",
                    type="agent",
                    description="A test step",
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Test prompt",
                    },
                ),
            ],
        )

        response = await validate_workflow(request)

        assert response.valid is True
        assert len(response.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_workflow_with_warnings(self):
        """Test validating a workflow that produces warnings."""
        request = WorkflowCreateRequest(
            name="Test Workflow",
            workflow_type="custom",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="First Step",
                    type="agent",
                    # No description - should trigger warning
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Test prompt",
                    },
                ),
            ],
        )

        response = await validate_workflow(request)

        assert response.valid is True
        assert len(response.warnings) > 0


class TestCreateEndpoint:
    """Tests for /workflows/create endpoint."""

    @pytest.mark.asyncio
    async def test_create_workflow(self):
        """Test creating a workflow."""
        request = WorkflowCreateRequest(
            name="Created Workflow",
            description="A workflow created via API",
            workflow_type="reserve_calculation",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="Step 1",
                    type="agent",
                    description="First step",
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Test",
                    },
                ),
            ],
        )

        response = await create_workflow(request)

        assert response.name == "Created Workflow"
        assert response.workflow_type == "reserve_calculation"
        assert len(response.steps) == 1


class TestExportEndpoint:
    """Tests for /workflows/export/* endpoints."""

    @pytest.mark.asyncio
    async def test_export_yaml(self):
        """Test exporting workflow to YAML."""
        request = WorkflowCreateRequest(
            name="Export Test",
            workflow_type="custom",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="Step 1",
                    type="agent",
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Test",
                    },
                ),
            ],
        )

        response = await export_workflow_yaml(request)

        assert "name: Export Test" in response.yaml
        assert "workflow_type: custom" in response.yaml


class TestExecutionOrderEndpoint:
    """Tests for /workflows/execution-order endpoint."""

    @pytest.mark.asyncio
    async def test_get_execution_order(self):
        """Test getting execution order."""
        request = WorkflowCreateRequest(
            name="Order Test",
            workflow_type="custom",
            steps=[
                WorkflowStep(
                    id="step1",
                    name="Step 1",
                    type="agent",
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Step 1",
                    },
                ),
                WorkflowStep(
                    id="step2",
                    name="Step 2",
                    type="agent",
                    depends_on=["step1"],
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Step 2",
                    },
                ),
                WorkflowStep(
                    id="step3",
                    name="Step 3",
                    type="agent",
                    depends_on=["step2"],
                    agent={
                        "agent_type": "general",
                        "prompt_template": "Step 3",
                    },
                ),
            ],
        )

        response = await get_execution_order(request)

        assert len(response.levels) == 3
        assert "step1" in response.levels[0]
        assert "step2" in response.levels[1]
        assert "step3" in response.levels[2]
