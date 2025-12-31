"""
Output guardrails for policy enforcement.

These guardrails run after agent execution to validate outputs against
policy requirements, particularly for actuarial compliance.
"""

import re
from typing import Any

from agents import Agent, OutputGuardrail, GuardrailFunctionOutput
from agents.run_context import RunContextWrapper

from core.logging import get_logger
from guardrails.policy import (
    DEFAULT_POLICY_CONFIG,
    PolicyGuardrailConfig,
    PolicyGuardrailResult,
    PolicyViolation,
    PolicyViolationType,
)

logger = get_logger(__name__)


# Patterns for detecting numerical outputs that need artefact references
NUMERICAL_PATTERNS = [
    r"(?:R|ZAR|USD|\$|€|£)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|m|bn))?",  # Currency amounts
    r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*%",  # Percentages
    r"(?:reserve|IBNR|CSM|RA|LIC|BEL|risk adjustment)\s*(?:of|is|=|:)?\s*R?\s*[\d,]+",  # Actuarial values
    r"\b(?:loss ratio|combined ratio|MLR|expense ratio)\s*(?:of|is|=|:)?\s*\d+(?:\.\d+)?\s*%?",  # Ratios
]

# Patterns for artefact references
ARTEFACT_REFERENCE_PATTERNS = [
    r"(?:artefact|artifact|model|calculation|worksheet)\s*(?:id|ref|reference|#)?\s*[:=]?\s*[A-Z0-9\-]+",
    r"\[(?:REF|ARTEFACT|MODEL|CALC):\s*[A-Z0-9\-]+\]",
    r"(?:as per|per|see|reference|ref)\s+(?:artefact|artifact|model|calculation)\s+[A-Z0-9\-]+",
    r"Source:\s*[A-Z0-9\-]+",
]


def check_output_length(
    output_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if output length is within allowed limits.

    Args:
        output_text: The output text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []

    if len(output_text) > config.max_output_length:
        violations.append(
            PolicyViolation(
                violation_type=PolicyViolationType.OUTPUT_TOO_LONG,
                message=f"Output exceeds maximum length of {config.max_output_length} characters.",
                details={
                    "actual_length": len(output_text),
                    "max_length": config.max_output_length,
                },
            )
        )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        metadata={"output_length": len(output_text)},
    )


def check_sensitive_data_output(
    output_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if output contains sensitive data patterns.

    Args:
        output_text: The output text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []

    if not config.block_sensitive_data_output:
        return PolicyGuardrailResult(passed=True)

    for pattern in config.sensitive_data_patterns:
        # Skip email addresses in output (they may be legitimate references)
        if pattern.name == "email_address":
            continue

        matches = re.findall(pattern.pattern, output_text)
        if matches:
            violations.append(
                PolicyViolation(
                    violation_type=PolicyViolationType.SENSITIVE_DATA_OUTPUT,
                    message=f"Output contains potentially sensitive data: {pattern.description}",
                    details={
                        "pattern_name": pattern.name,
                        "match_count": len(matches),
                    },
                )
            )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        metadata={"patterns_checked": len(config.sensitive_data_patterns)},
    )


def _find_numerical_outputs(text: str) -> list[dict[str, Any]]:
    """
    Find numerical outputs in text that may require artefact references.

    Args:
        text: Text to search

    Returns:
        List of found numerical outputs with their positions
    """
    numerical_outputs = []
    for pattern in NUMERICAL_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            numerical_outputs.append({
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return numerical_outputs


def _has_artefact_reference(text: str, numerical_output: dict[str, Any]) -> bool:
    """
    Check if a numerical output has an associated artefact reference.

    Looks for references within a reasonable distance of the numerical value.

    Args:
        text: Full text to search
        numerical_output: The numerical output to check

    Returns:
        True if an artefact reference is found nearby
    """
    # Search within 500 characters before and after the number
    search_start = max(0, numerical_output["start"] - 500)
    search_end = min(len(text), numerical_output["end"] + 500)
    search_text = text[search_start:search_end]

    for pattern in ARTEFACT_REFERENCE_PATTERNS:
        if re.search(pattern, search_text, re.IGNORECASE):
            return True

    return False


def check_artefact_references(
    output_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if numerical outputs have proper artefact references.

    This is a key actuarial governance requirement - all numbers must be
    traceable to their source models/calculations.

    Args:
        output_text: The output text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []
    warnings = []

    if not config.require_artefact_references:
        return PolicyGuardrailResult(passed=True)

    numerical_outputs = _find_numerical_outputs(output_text)

    unreferenced_values = []
    for num_output in numerical_outputs:
        if not _has_artefact_reference(output_text, num_output):
            unreferenced_values.append(num_output["value"])

    # If more than 2 unreferenced numerical values, it's a violation
    # Otherwise it's a warning (could be general discussion)
    if len(unreferenced_values) > 2:
        violations.append(
            PolicyViolation(
                violation_type=PolicyViolationType.MISSING_ARTEFACT_REFERENCE,
                message="Multiple numerical outputs without artefact references",
                details={
                    "unreferenced_values": unreferenced_values[:5],  # Limit to first 5
                    "total_unreferenced": len(unreferenced_values),
                },
            )
        )
    elif unreferenced_values:
        warnings.append(
            PolicyViolation(
                violation_type=PolicyViolationType.MISSING_ARTEFACT_REFERENCE,
                message="Some numerical outputs may need artefact references",
                details={
                    "unreferenced_values": unreferenced_values,
                },
                severity="warning",
            )
        )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        metadata={
            "numerical_outputs_found": len(numerical_outputs),
            "unreferenced_count": len(unreferenced_values),
        },
    )


def _extract_output_text(agent_output: Any) -> str:
    """
    Extract text content from agent output.

    Args:
        agent_output: The agent's output (can be various types)

    Returns:
        String representation of the output
    """
    if isinstance(agent_output, str):
        return agent_output

    if hasattr(agent_output, "final_output"):
        return str(agent_output.final_output)

    if hasattr(agent_output, "content"):
        return str(agent_output.content)

    return str(agent_output)


async def policy_output_guardrail_function(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    agent_output: Any,
    config: PolicyGuardrailConfig | None = None,
) -> GuardrailFunctionOutput:
    """
    Combined policy guardrail function for output validation.

    This function runs all output policy checks and returns a combined result.

    Args:
        ctx: Run context wrapper
        agent: The agent that produced the output
        agent_output: The output to validate
        config: Policy configuration (uses default if not provided)

    Returns:
        GuardrailFunctionOutput with tripwire status and output info
    """
    config = config or DEFAULT_POLICY_CONFIG
    output_text = _extract_output_text(agent_output)

    all_violations = []
    all_warnings = []
    metadata = {"agent_name": agent.name}

    # Run all checks
    checks = [
        ("length", check_output_length(output_text, config)),
        ("sensitive_data", check_sensitive_data_output(output_text, config)),
        ("artefact_references", check_artefact_references(output_text, config)),
    ]

    for check_name, result in checks:
        all_violations.extend(result.violations)
        all_warnings.extend(result.warnings)
        metadata[check_name] = result.metadata

    # Log violations
    if all_violations:
        logger.warning(
            "Policy output guardrail triggered",
            agent_name=agent.name,
            violation_count=len(all_violations),
            violations=[v.violation_type.value for v in all_violations],
        )

    tripwire_triggered = len(all_violations) > 0

    return GuardrailFunctionOutput(
        output_info={
            "passed": not tripwire_triggered,
            "violations": [v.to_dict() for v in all_violations],
            "warnings": [w.to_dict() for w in all_warnings],
            "metadata": metadata,
        },
        tripwire_triggered=tripwire_triggered,
    )


def create_policy_output_guardrail(
    config: PolicyGuardrailConfig | None = None,
    name: str = "policy_output_guardrail",
) -> OutputGuardrail[Any]:
    """
    Create an OutputGuardrail with policy enforcement.

    Args:
        config: Policy configuration (uses default if not provided)
        name: Name for the guardrail (for tracing)

    Returns:
        Configured OutputGuardrail instance
    """
    config = config or DEFAULT_POLICY_CONFIG

    async def guardrail_func(
        ctx: RunContextWrapper[Any],
        agent: Agent[Any],
        agent_output: Any,
    ) -> GuardrailFunctionOutput:
        return await policy_output_guardrail_function(ctx, agent, agent_output, config)

    return OutputGuardrail(
        guardrail_function=guardrail_func,
        name=name,
    )
