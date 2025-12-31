"""
Policy guardrail configuration and result types.

Defines the policy layer for enforcing business rules and compliance
requirements across all agent interactions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PolicyViolationType(str, Enum):
    """Types of policy violations that can be detected."""

    # Input violations
    INPUT_TOO_LONG = "input_too_long"
    PROHIBITED_TOPIC = "prohibited_topic"
    SENSITIVE_DATA_INPUT = "sensitive_data_input"
    UNAUTHORIZED_ACTION = "unauthorized_action"

    # Output violations
    OUTPUT_TOO_LONG = "output_too_long"
    MISSING_ARTEFACT_REFERENCE = "missing_artefact_reference"
    SENSITIVE_DATA_OUTPUT = "sensitive_data_output"
    UNVERIFIED_NUMERICAL_CLAIM = "unverified_numerical_claim"

    # General violations
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    COMPLIANCE_VIOLATION = "compliance_violation"


@dataclass
class PolicyViolation:
    """
    Represents a single policy violation detected by a guardrail.

    Attributes:
        violation_type: The type of violation
        message: Human-readable description of the violation
        details: Additional context about the violation
        severity: Severity level (error, warning, info)
    """

    violation_type: PolicyViolationType
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        """Convert violation to dictionary for API responses."""
        return {
            "type": self.violation_type.value,
            "message": self.message,
            "details": self.details,
            "severity": self.severity,
        }


@dataclass
class PolicyGuardrailResult:
    """
    Result of a policy guardrail check.

    Attributes:
        passed: Whether the check passed
        violations: List of violations if check failed
        warnings: List of non-blocking warnings
        metadata: Additional metadata from the check
    """

    passed: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    warnings: list[PolicyViolation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for API responses."""
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "metadata": self.metadata,
        }


class SensitiveDataPattern(BaseModel):
    """Pattern for detecting sensitive data."""

    name: str = Field(description="Name of the sensitive data type")
    pattern: str = Field(description="Regex pattern to match")
    description: str = Field(description="Description of what this pattern detects")


class PolicyGuardrailConfig(BaseModel):
    """
    Configuration for policy-level guardrails.

    This configuration defines the business rules and compliance requirements
    that agents must adhere to.
    """

    # Input validation settings
    max_input_length: int = Field(
        default=32000,
        description="Maximum allowed input length in characters",
    )
    min_input_length: int = Field(
        default=1,
        description="Minimum required input length in characters",
    )

    # Output validation settings
    max_output_length: int = Field(
        default=16000,
        description="Maximum allowed output length in characters",
    )
    require_artefact_references: bool = Field(
        default=True,
        description="Whether numerical outputs must reference model artefacts",
    )

    # Sensitive data settings
    block_sensitive_data_input: bool = Field(
        default=True,
        description="Block inputs containing sensitive data patterns",
    )
    block_sensitive_data_output: bool = Field(
        default=True,
        description="Block outputs containing sensitive data patterns",
    )
    sensitive_data_patterns: list[SensitiveDataPattern] = Field(
        default_factory=lambda: [
            SensitiveDataPattern(
                name="credit_card",
                pattern=r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b",
                description="Credit card numbers",
            ),
            SensitiveDataPattern(
                name="south_african_id",
                pattern=r"\b[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{4}[01][0-9]{2}\b",
                description="South African ID numbers",
            ),
            SensitiveDataPattern(
                name="email_address",
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                description="Email addresses (blocked in certain contexts)",
            ),
            SensitiveDataPattern(
                name="phone_number",
                pattern=r"\b(?:\+27|0)(?:\d{9}|\d{2}[-\s]?\d{3}[-\s]?\d{4})\b",
                description="South African phone numbers",
            ),
            SensitiveDataPattern(
                name="api_key",
                pattern=r"\b(?:sk-[a-zA-Z0-9]{20,}|xox[baprs]-[a-zA-Z0-9-]+|ghp_[a-zA-Z0-9]{36})\b",
                description="API keys (OpenAI, Slack, GitHub)",
            ),
        ],
        description="Patterns for detecting sensitive data",
    )

    # Prohibited topics
    prohibited_topics: list[str] = Field(
        default_factory=lambda: [
            "how to commit fraud",
            "money laundering",
            "insider trading",
            "circumvent audit",
            "hide losses",
            "falsify records",
            "manipulate reserves",
        ],
        description="Topics that should be blocked",
    )

    # Actuarial-specific settings
    require_methodology_citation: bool = Field(
        default=True,
        description="Require actuarial methods to be cited",
    )
    require_assumption_disclosure: bool = Field(
        default=True,
        description="Require key assumptions to be disclosed",
    )

    # Compliance requirements
    professional_standards: list[str] = Field(
        default_factory=lambda: [
            "ASSA",  # Actuarial Society of South Africa
            "IAA",   # International Actuarial Association
            "IFRS17",
            "SAM",   # Solvency Assessment and Management
        ],
        description="Professional standards that must be referenced",
    )

    # Actions requiring approval
    actions_requiring_approval: list[str] = Field(
        default_factory=lambda: [
            "finalize_reserves",
            "submit_report",
            "approve_disclosure",
            "release_to_client",
        ],
        description="Actions that require human approval",
    )


# Default policy configuration
DEFAULT_POLICY_CONFIG = PolicyGuardrailConfig()
