"""
Custom exception classes and error handling utilities.

Provides domain-specific exceptions with structured error responses
following the project's "no silent failures" policy.
"""

from typing import Any, NoReturn

from fastapi import HTTPException, status


class AppError(Exception):
    """
    Base application error with structured error information.

    All custom exceptions should inherit from this class to ensure
    consistent error handling and logging.
    """

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "APP_ERROR"
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigurationError(AppError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


class ValidationError(AppError):
    """Raised when input validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class AuthenticationError(AppError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, code="AUTHENTICATION_ERROR")


class AuthorizationError(AppError):
    """Raised when user lacks permission for an action."""

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, code="AUTHORIZATION_ERROR")


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str | None = None,
    ) -> None:
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} with id '{resource_id}' not found"
        super().__init__(message, code="NOT_FOUND", details={"resource_type": resource_type})


class ExternalServiceError(AppError):
    """Raised when an external service (OpenAI, Supabase) fails."""

    def __init__(
        self,
        service: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, **(details or {})},
        )


class AgentExecutionError(AppError):
    """Raised when an AI agent execution fails."""

    def __init__(
        self,
        agent_name: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Agent '{agent_name}' failed: {message}",
            code="AGENT_EXECUTION_ERROR",
            details={"agent": agent_name, **(details or {})},
        )


def raise_http_error(
    status_code: int,
    message: str,
    code: str | None = None,
    details: dict[str, Any] | None = None,
) -> NoReturn:
    """
    Raise an HTTPException with structured error detail.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        code: Machine-readable error code
        details: Additional error details

    Raises:
        HTTPException: Always raises

    Example:
        raise_http_error(404, "Engagement not found", "ENGAGEMENT_NOT_FOUND")
    """
    raise HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code or "ERROR",
                "message": message,
                "details": details or {},
            }
        },
    )


def raise_not_found(resource_type: str, resource_id: str | None = None) -> NoReturn:
    """Convenience function to raise a 404 error."""
    message = f"{resource_type} not found"
    if resource_id:
        message = f"{resource_type} with id '{resource_id}' not found"
    raise_http_error(
        status.HTTP_404_NOT_FOUND,
        message,
        "NOT_FOUND",
        {"resource_type": resource_type, "resource_id": resource_id},
    )


def raise_validation_error(message: str, details: dict[str, Any] | None = None) -> NoReturn:
    """Convenience function to raise a 422 validation error."""
    raise_http_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        message,
        "VALIDATION_ERROR",
        details,
    )


def raise_unauthorized(message: str = "Authentication required") -> NoReturn:
    """Convenience function to raise a 401 error."""
    raise_http_error(status.HTTP_401_UNAUTHORIZED, message, "UNAUTHORIZED")


def raise_forbidden(message: str = "Permission denied") -> NoReturn:
    """Convenience function to raise a 403 error."""
    raise_http_error(status.HTTP_403_FORBIDDEN, message, "FORBIDDEN")
