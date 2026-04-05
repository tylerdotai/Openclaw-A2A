"""
OpenClaw A2A — Custom Exceptions

All errors are production-ready with structured context.
No secrets leaked in error messages.
"""

from __future__ import annotations

from typing import Any, Optional


class OpenClawA2AError(Exception):
    """Base exception for all OpenClaw A2A errors."""

    _default_code = "A2A_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code if code is not None else self._default_code
        self.details = details or {}
        self.cause = cause

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ── Transport / Network ────────────────────────────────────────────────────────


class TransportError(OpenClawA2AError):
    """Base transport error (network, HTTP, timeout)."""

    _default_code = "TRANSPORT_ERROR"


class ConnectionError(TransportError):
    """Could not connect to remote agent."""

    _default_code = "CONNECTION_ERROR"


class TimeoutError(TransportError):
    """Request timed out."""

    _default_code = "TIMEOUT"


class StreamingError(OpenClawA2AError):
    """SSE / streaming channel failed."""

    _default_code = "STREAMING_ERROR"


# ── Authentication / Authorization ────────────────────────────────────────────


class AuthError(OpenClawA2AError):
    """Authentication or authorization failed."""

    _default_code = "AUTH_ERROR"


class APIKeyError(AuthError):
    """Invalid or missing API key."""

    _default_code = "API_KEY_ERROR"


class JWTArror(AuthError):
    """JWT validation failed."""

    _default_code = "JWT_ERROR"


# ── Tasks ──────────────────────────────────────────────────────────────────────


class TaskNotFoundError(OpenClawA2AError):
    """Requested task ID does not exist."""

    _default_code = "TASK_NOT_FOUND"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(
            f"Task not found: {task_id!r}",
            details={"task_id": task_id},
        )


class TaskCanceledError(OpenClawA2AError):
    """Task was canceled."""

    _default_code = "TASK_CANCELED"

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(
            f"Task was canceled: {task_id!r}",
            details={"task_id": task_id},
        )


class TaskStateError(OpenClawA2AError):
    """Invalid state transition for task."""

    _default_code = "TASK_STATE_ERROR"


# ── Agent Card ────────────────────────────────────────────────────────────────


class AgentCardError(OpenClawA2AError):
    """Agent Card validation or fetch failed."""

    _default_code = "AGENT_CARD_ERROR"


class AgentNotFoundError(AgentCardError):
    """Agent not found in registry/discovery."""

    _default_code = "AGENT_NOT_FOUND"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(
            f"Agent not found: {agent_id!r}",
            details={"agent_id": agent_id},
        )


# ── Tracing / Audit ───────────────────────────────────────────────────────────


class TraceError(OpenClawA2AError):
    """Trace context propagation failed."""

    _default_code = "TRACE_ERROR"


class AuditError(OpenClawA2AError):
    """Audit logging failed (non-fatal, logged as warning)."""

    _default_code = "AUDIT_ERROR"


# ── Server / Protocol ─────────────────────────────────────────────────────────


class ServerError(OpenClawA2AError):
    """A2A server returned an error response."""

    _default_code = "SERVER_ERROR"

    def __init__(self, status_code: int, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.status_code = status_code
        super().__init__(
            f"Server error ({status_code}): {message}",
            details={**(details or {}), "status_code": status_code},
        )


class InvalidRequestError(ServerError):
    """Malformed request (4xx)."""

    _default_code = "INVALID_REQUEST"

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.status_code = 400
        super().__init__(400, message, details)
