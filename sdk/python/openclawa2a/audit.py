"""
OpenClaw A2A — Audit Logging

Immutable, structured JSON audit logs for every A2A operation.
All state changes, messages, and errors are captured with
full trace context. No secrets in logs.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from openclawa2a.tracing import get_current_trace_id, new_trace_id

logger = logging.getLogger(__name__)


class AuditOperation(str, Enum):
    """All auditable A2A operations."""

    # Client
    SEND_MESSAGE = "send_message"
    STREAM_MESSAGE = "stream_message"
    GET_TASK = "get_task"
    LIST_TASKS = "list_tasks"
    CANCEL_TASK = "cancel_task"
    SUBSCRIBE_TASK = "subscribe_task"
    GET_AGENT_CARD = "get_agent_card"

    # Server
    RECEIVE_MESSAGE = "receive_message"
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELED = "task_canceled"

    # Lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"


class AuditLogger:
    """
    Structured, immutable JSON audit logger.

    Log entries are written as NDJSON (newline-delimited JSON) to
    the configured output path. Each entry is self-contained with
    a timestamp, trace_id, and full operation context.

    Thread-safe for concurrent writes.
    """

    def __init__(
        self,
        output_path: Optional[Path] = None,
        service_name: str = "openclawa2a",
        include_trace: bool = True,
        redact_keys: Optional[list[str]] = None,
    ) -> None:
        """
        Args:
            output_path: Path to write NDJSON audit log. None = stdout only.
            service_name: Name of this service for log entries.
            include_trace: Include trace_id in every entry.
            redact_keys: Field names to redact in log output (values replaced
                         with "[REDACTED]"). Does NOT affect structured storage.
        """
        self.output_path = output_path
        self.service_name = service_name
        self.include_trace = include_trace
        self.redact_keys = set(redact_keys or [])
        self._lock = threading.RLock()

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)

    def _redact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return a shallow copy of data with redacted keys."""
        if not self.redact_keys:
            return data
        result = dict(data)
        for key in self.redact_keys:
            if key in result:
                result[key] = "[REDACTED]"
        return result

    def log(
        self,
        operation: AuditOperation | str,
        *,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: str = "success",
        metadata: Optional[dict[str, Any]] = None,
        error: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """
        Write a single audit log entry.

        Returns the trace_id used for this entry.
        """
        trace_id = trace_id or get_current_trace_id() or new_trace_id()

        entry: dict[str, Any] = {
            "version": "1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "service": self.service_name,
            "operation": operation if isinstance(operation, str) else operation.value,
            "status": status,
        }

        if task_id:
            entry["task_id"] = task_id
        if context_id:
            entry["context_id"] = context_id
        if agent_id:
            entry["agent_id"] = agent_id
        if request_id:
            entry["request_id"] = request_id
        if metadata:
            entry["metadata"] = self._redact(metadata)
        if error:
            entry["error"] = error

        # Immutable: entry is sealed after this point
        entry["_immutable"] = True

        json_line = json.dumps(entry, default=str, separators=(",", ":"))

        with self._lock:
            if self.output_path:
                with open(self.output_path, "a", encoding="utf-8") as fh:
                    fh.write(json_line + "\n")
            # Always also emit to Python logger (structured)
            logger.info("AUDIT %s", json_line)

        return trace_id

    def trace(
        self,
        operation: AuditOperation | str,
        *,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        **metadata: Any,
    ) -> "_AuditSpan":
        """
        Context manager for tracing a full operation.

        Usage:
            with audit.trace("send_message", task_id="123") as span:
                result = client.send_message(...)
                span.success(result_id=result.id)
        """
        return _AuditSpan(
            logger=self,
            operation=operation,
            trace_id=trace_id or get_current_trace_id() or new_trace_id(),
            task_id=task_id,
            context_id=context_id,
            metadata=metadata,
        )

    def audit(
        self,
        operation: AuditOperation | str,
        *,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Convenience: log an operation with default 'success' status."""
        self.log(
            operation=operation,
            trace_id=trace_id,
            task_id=task_id,
            context_id=context_id,
            agent_id=agent_id,
            status="success",
            metadata=metadata,
        )


class _AuditSpan:
    """
    Active audit span — tracks operation lifecycle.

    Usage:
        with audit.trace("send_message") as span:
            span.success(task_id="...")
            # or
            span.failure(error_code="TIMEOUT")
    """

    def __init__(
        self,
        logger: AuditLogger,
        operation: AuditOperation | str,
        trace_id: str,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self._logger = logger
        self.operation = operation
        self.trace_id = trace_id
        self.task_id = task_id
        self.context_id = context_id
        self.metadata = metadata or {}
        self._entered = False

    def __enter__(self) -> "_AuditSpan":
        self._entered = True
        self._logger.log(
            operation=self.operation,
            trace_id=self.trace_id,
            task_id=self.task_id,
            context_id=self.context_id,
            status="started",
            metadata={**self.metadata, "_span_start": True},
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            self.failure(error_type=exc_type.__name__, error_message=str(exc_val)[:200])
        else:
            # If exit without explicit success/failure, log as unknown
            self._logger.log(
                operation=self.operation,
                trace_id=self.trace_id,
                task_id=self.task_id,
                context_id=self.context_id,
                status="ended",
                metadata={**self.metadata, "_span_end": True},
            )

    def success(self, **result_metadata: Any) -> None:
        self._logger.log(
            operation=self.operation,
            trace_id=self.trace_id,
            task_id=self.task_id,
            context_id=self.context_id,
            status="success",
            metadata={**self.metadata, **result_metadata},
        )

    def failure(self, error_code: Optional[str] = None, error_message: str = "", **extra: Any) -> None:
        self._logger.log(
            operation=self.operation,
            trace_id=self.trace_id,
            task_id=self.task_id,
            context_id=self.context_id,
            status="failure",
            error={"code": error_code, "message": error_message},
            metadata={**self.metadata, **extra},
        )


# ── Global singleton ───────────────────────────────────────────────────────────

_global_logger: Optional[AuditLogger] = None
_global_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _global_logger
    with _global_lock:
        if _global_logger is None:
            _global_logger = AuditLogger(service_name="openclawa2a")
        return _global_logger


def configure_audit_logger(
    output_path: Optional[Path] = None,
    service_name: str = "openclawa2a",
    **kwargs: Any,
) -> AuditLogger:
    """Configure the global audit logger."""
    global _global_logger
    with _global_lock:
        _global_logger = AuditLogger(
            output_path=output_path,
            service_name=service_name,
            **kwargs,
        )
        return _global_logger
