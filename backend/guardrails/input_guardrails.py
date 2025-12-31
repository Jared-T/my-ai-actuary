"""
Input guardrails for policy enforcement.

These guardrails run before or in parallel with agent execution to validate
inputs against policy requirements.
"""

import re
from typing import Any, Union

from agents import Agent, InputGuardrail, GuardrailFunctionOutput
from agents.run_context import RunContextWrapper
from agents.items import TResponseInputItem

from core.logging import get_logger
from guardrails.policy import (
    DEFAULT_POLICY_CONFIG,
    PolicyGuardrailConfig,
    PolicyGuardrailResult,
    PolicyViolation,
    PolicyViolationType,
)

logger = get_logger(__name__)


def check_input_length(
    input_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if input length is within allowed limits.

    Args:
        input_text: The input text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []

    if len(input_text) < config.min_input_length:
        violations.append(
            PolicyViolation(
                violation_type=PolicyViolationType.INPUT_TOO_LONG,
                message=f"Input too short. Minimum length is {config.min_input_length} characters.",
                details={
                    "actual_length": len(input_text),
                    "min_length": config.min_input_length,
                },
            )
        )

    if len(input_text) > config.max_input_length:
        violations.append(
            PolicyViolation(
                violation_type=PolicyViolationType.INPUT_TOO_LONG,
                message=f"Input exceeds maximum length of {config.max_input_length} characters.",
                details={
                    "actual_length": len(input_text),
                    "max_length": config.max_input_length,
                },
            )
        )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        metadata={"input_length": len(input_text)},
    )


def check_prohibited_topics(
    input_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if input contains prohibited topics.

    Args:
        input_text: The input text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []
    input_lower = input_text.lower()

    for topic in config.prohibited_topics:
        if topic.lower() in input_lower:
            violations.append(
                PolicyViolation(
                    violation_type=PolicyViolationType.PROHIBITED_TOPIC,
                    message=f"Input contains prohibited topic: '{topic}'",
                    details={"prohibited_topic": topic},
                )
            )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        metadata={"topics_checked": len(config.prohibited_topics)},
    )


def check_sensitive_data_input(
    input_text: str,
    config: PolicyGuardrailConfig | None = None,
) -> PolicyGuardrailResult:
    """
    Check if input contains sensitive data patterns.

    Args:
        input_text: The input text to check
        config: Policy configuration (uses default if not provided)

    Returns:
        PolicyGuardrailResult indicating pass/fail
    """
    config = config or DEFAULT_POLICY_CONFIG
    violations = []
    warnings = []

    if not config.block_sensitive_data_input:
        return PolicyGuardrailResult(passed=True)

    for pattern in config.sensitive_data_patterns:
        matches = re.findall(pattern.pattern, input_text)
        if matches:
            # Email addresses are warnings, not violations
            if pattern.name == "email_address":
                warnings.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.SENSITIVE_DATA_INPUT,
                        message=f"Input may contain {pattern.description}",
                        details={
                            "pattern_name": pattern.name,
                            "match_count": len(matches),
                        },
                        severity="warning",
                    )
                )
            else:
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.SENSITIVE_DATA_INPUT,
                        message=f"Input contains potentially sensitive data: {pattern.description}",
                        details={
                            "pattern_name": pattern.name,
                            "match_count": len(matches),
                        },
                    )
                )

    return PolicyGuardrailResult(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        metadata={"patterns_checked": len(config.sensitive_data_patterns)},
    )


def _extract_input_text(
    input_data: Union[str, list[TResponseInputItem]],
) -> str:
    """
    Extract text content from input data.

    Args:
        input_data: Either a string or list of response input items

    Returns:
        Combined text content
    """
    if isinstance(input_data, str):
        return input_data

    # Handle list of input items
    texts = []
    for item in input_data:
        if isinstance(item, str):
            texts.append(item)
        elif hasattr(item, "content"):
            content = item.content
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for c in content:
                    if hasattr(c, "text"):
                        texts.append(c.text)
                    elif isinstance(c, str):
                        texts.append(c)
        elif isinstance(item, dict) and "content" in item:
            texts.append(str(item["content"]))

    return "\n".join(texts)


async def policy_input_guardrail_function(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    input_data: Union[str, list[TResponseInputItem]],
    config: PolicyGuardrailConfig | None = None,
) -> GuardrailFunctionOutput:
    """
    Combined policy guardrail function for input validation.

    This function runs all input policy checks and returns a combined result.

    Args:
        ctx: Run context wrapper
        agent: The agent being run
        input_data: Input text or list of input items
        config: Policy configuration (uses default if not provided)

    Returns:
        GuardrailFunctionOutput with tripwire status and output info
    """
    config = config or DEFAULT_POLICY_CONFIG
    input_text = _extract_input_text(input_data)

    all_violations = []
    all_warnings = []
    metadata = {"agent_name": agent.name}

    # Run all checks
    checks = [
        ("length", check_input_length(input_text, config)),
        ("prohibited_topics", check_prohibited_topics(input_text, config)),
        ("sensitive_data", check_sensitive_data_input(input_text, config)),
    ]

    for check_name, result in checks:
        all_violations.extend(result.violations)
        all_warnings.extend(result.warnings)
        metadata[check_name] = result.metadata

    # Log violations
    if all_violations:
        logger.warning(
            "Policy input guardrail triggered",
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


def create_policy_input_guardrail(
    config: PolicyGuardrailConfig | None = None,
    name: str = "policy_input_guardrail",
    run_in_parallel: bool = False,
) -> InputGuardrail[Any]:
    """
    Create an InputGuardrail with policy enforcement.

    Args:
        config: Policy configuration (uses default if not provided)
        name: Name for the guardrail (for tracing)
        run_in_parallel: Whether to run in parallel with agent (default: False)

    Returns:
        Configured InputGuardrail instance
    """
    config = config or DEFAULT_POLICY_CONFIG

    async def guardrail_func(
        ctx: RunContextWrapper[Any],
        agent: Agent[Any],
        input_data: Union[str, list[TResponseInputItem]],
    ) -> GuardrailFunctionOutput:
        return await policy_input_guardrail_function(ctx, agent, input_data, config)

    return InputGuardrail(
        guardrail_function=guardrail_func,
        name=name,
        run_in_parallel=run_in_parallel,
    )
