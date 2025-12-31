"""
Base function tools for agents using OpenAI Agents SDK.

Provides common tools that can be used by multiple agents.
Uses the @function_tool decorator from the agents SDK.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from agents import function_tool


@function_tool
def get_current_datetime() -> str:
    """
    Get the current date and time in ISO format.

    Returns:
        Current datetime as ISO format string in UTC.
    """
    now = datetime.now(timezone.utc)
    return now.isoformat()


@function_tool
def format_currency(amount: float, currency: str = "USD", decimals: int = 2) -> str:
    """
    Format a numeric amount as currency.

    Args:
        amount: The numeric amount to format
        currency: The currency code (default: USD)
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted currency string
    """
    formatted = f"{amount:,.{decimals}f}"
    currency_symbols = {
        "USD": "$",
        "EUR": "\u20ac",
        "GBP": "\u00a3",
        "ZAR": "R",
    }
    symbol = currency_symbols.get(currency, currency + " ")
    return f"{symbol}{formatted}"


@function_tool
def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format a decimal value as a percentage.

    Args:
        value: The decimal value (e.g., 0.15 for 15%)
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted percentage string
    """
    percentage = value * 100
    return f"{percentage:.{decimals}f}%"


@function_tool
def calculate_change_percentage(old_value: float, new_value: float) -> str:
    """
    Calculate the percentage change between two values.

    Args:
        old_value: The original value
        new_value: The new value

    Returns:
        Formatted percentage change string with direction indicator
    """
    if old_value == 0:
        return "N/A (division by zero)"

    change = ((new_value - old_value) / old_value) * 100
    direction = "+" if change >= 0 else ""
    return f"{direction}{change:.2f}%"


@function_tool
def validate_uuid(uuid_string: str) -> dict[str, Any]:
    """
    Validate if a string is a valid UUID.

    Args:
        uuid_string: The string to validate

    Returns:
        Dictionary with validation result and parsed UUID if valid
    """
    try:
        parsed = UUID(uuid_string)
        return {
            "valid": True,
            "uuid": str(parsed),
            "version": parsed.version,
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": str(e),
        }


@function_tool
def summarize_numbers(numbers: list[float]) -> dict[str, float]:
    """
    Calculate summary statistics for a list of numbers.

    Args:
        numbers: List of numeric values

    Returns:
        Dictionary with sum, mean, min, max, and count
    """
    if not numbers:
        return {
            "count": 0,
            "sum": 0.0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    return {
        "count": len(numbers),
        "sum": sum(numbers),
        "mean": sum(numbers) / len(numbers),
        "min": min(numbers),
        "max": max(numbers),
    }


@function_tool
def create_table_markdown(
    headers: list[str],
    rows: list[list[str]],
    alignment: str = "left",
) -> str:
    """
    Create a markdown table from headers and rows.

    Args:
        headers: List of column headers
        rows: List of rows, where each row is a list of cell values
        alignment: Column alignment ('left', 'center', 'right')

    Returns:
        Markdown table string
    """
    if not headers:
        return ""

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Alignment characters
    align_chars = {
        "left": ":---",
        "center": ":---:",
        "right": "---:",
    }
    align = align_chars.get(alignment, ":---")

    # Build table
    lines = []

    # Header row
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines.append(header_line)

    # Separator row
    sep_line = "| " + " | ".join(align.ljust(widths[i], "-") for i in range(len(headers))) + " |"
    lines.append(sep_line)

    # Data rows
    for row in rows:
        row_cells = []
        for i in range(len(headers)):
            cell = str(row[i]) if i < len(row) else ""
            row_cells.append(cell.ljust(widths[i]))
        lines.append("| " + " | ".join(row_cells) + " |")

    return "\n".join(lines)


# Export all tools for easy import
BASE_TOOLS = [
    get_current_datetime,
    format_currency,
    format_percentage,
    calculate_change_percentage,
    validate_uuid,
    summarize_numbers,
    create_table_markdown,
]
