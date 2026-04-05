"""
A2A Audit Extension — Brad's A2A-specific audit logger with SDK compatibility.

This module provides:
- A2AAuditLogger: Brad's production-grade logger with A2A event types and daily rolling logs
- AuditLoggerAdapter: Bridges A2AAuditLogger to the SDK's AuditLogger interface

Usage:
    # Direct A2A-specific logging:
    from openclawa2a.a2a_audit import A2AAuditLogger

    logger = A2AAuditLogger(log_dir="audit/logs")
    logger.task_created(source="dexter", target="hoss", task_id="123", content="Research task")

    # Use with SDK client (adapter pattern):
    from openclawa2a.a2a_audit import A2AAuditLogger, AuditLoggerAdapter

    a2a_logger = A2AAuditLogger(log_dir="audit/logs")
    adapter = AuditLoggerAdapter(a2a_logger)
    client = OpenClawA2AClient(url, audit_logger=adapter)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

__all__ = [
    "A2AAuditLogger",
    "AuditLoggerAdapter",
    "AUDIT_VERSION",
]

AUDIT_VERSION = "1.0.0"


class A2AAuditLogger:
    """
    Brad's A2A-specific audit logger.

    Structured audit logger for A2A agent-to-agent communications.
    Logs to daily rolling JSONL files with A2A-specific event types.

    Unlike the generic SDK AuditLogger, this one is purpose-built for
    tracking task delegation, message passing, and skill invocation
    across the agent mesh.
    """

    # A2A event types
    EVENT_TASK_CREATED = "task_created"
    EVENT_TASK_UPDATED = "task_updated"
    EVENT_MESSAGE_SENT = "message_sent"
    EVENT_MESSAGE_RECEIVED = "message_received"
    EVENT_AGENT_DISCOVERED = "agent_discovered"
    EVENT_SKILL_INVOKED = "skill_invoked"
    EVENT_ERROR = "error"

    # Status values
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "cancelled"

    def __init__(
        self,
        log_dir: str = "audit/logs",
        service_name: str = "openclawa2a",
    ) -> None:
        """
        Args:
            log_dir: Directory for daily rolling JSONL log files.
            service_name: Service identifier for log entries.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.service_name = service_name
        self.logger = logging.getLogger("a2a.audit")
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            )

    def _write(self, entry: dict) -> None:
        """Write a log entry to the daily rolling JSONL file."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"a2a-audit-{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log(
        self,
        event_type: str,
        source: str,
        target: str,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None,
        content: str = "",
        status: str = "pending",
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Log an A2A event.

        Returns the log entry dict that was written.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": AUDIT_VERSION,
            "service": self.service_name,
            "event_type": event_type,
            "source_agent": source,
            "target_agent": target,
            "task_id": task_id or str(uuid4()),
            "message_id": message_id or str(uuid4()),
            "content_summary": content[:200] if content else "",
            "status": status,
            "metadata": metadata or {},
        }

        self._write(entry)
        self.logger.info(f"[{event_type}] {source} → {target}: {status}")
        return entry

    # ── Convenience methods ────────────────────────────────────────────────────

    def task_created(
        self,
        source: str,
        target: str,
        task_id: str,
        content: str = "",
        **kwargs,
    ):
        return self.log(
            self.EVENT_TASK_CREATED,
            source,
            target,
            task_id=task_id,
            content=content,
            status=self.STATUS_PENDING,
            **kwargs,
        )

    def task_updated(
        self,
        source: str,
        target: str,
        task_id: str,
        status: str,
        **kwargs,
    ):
        return self.log(
            self.EVENT_TASK_UPDATED,
            source,
            target,
            task_id=task_id,
            status=status,
            **kwargs,
        )

    def message_sent(
        self,
        source: str,
        target: str,
        message_id: str,
        content: str = "",
        **kwargs,
    ):
        return self.log(
            self.EVENT_MESSAGE_SENT,
            source,
            target,
            message_id=message_id,
            content=content,
            **kwargs,
        )

    def message_received(
        self,
        source: str,
        target: str,
        message_id: str,
        content: str = "",
        **kwargs,
    ):
        return self.log(
            self.EVENT_MESSAGE_RECEIVED,
            source,
            target,
            message_id=message_id,
            content=content,
            **kwargs,
        )

    def agent_discovered(
        self,
        source: str,
        target: str,
        content: str = "",
        **kwargs,
    ):
        return self.log(
            self.EVENT_AGENT_DISCOVERED,
            source,
            target,
            content=content,
            **kwargs,
        )

    def skill_invoked(
        self,
        source: str,
        target: str,
        skill_id: str,
        **kwargs,
    ):
        return self.log(
            self.EVENT_SKILL_INVOKED,
            source,
            target,
            content=f"Skill: {skill_id}",
            **kwargs,
        )

    def error(
        self,
        source: str,
        target: str,
        error: str,
        **kwargs,
    ):
        return self.log(
            self.EVENT_ERROR,
            source,
            target,
            status=self.STATUS_FAILED,
            content=error,
            metadata={"error": error, **kwargs},
        )


# ── SDK AuditLogger compatibility adapter ──────────────────────────────────────


class AuditOperation(str, Enum):
    """Standard audit operations — maps SDK operations to A2A events."""

    SEND_MESSAGE = "send_message"
    GET_TASK = "get_task"
    LIST_TASKS = "list_tasks"
    CANCEL_TASK = "cancel_task"
    GET_AGENT_CARD = "get_agent_card"
    STREAM_EVENTS = "stream_events"
    SUBSCRIBE = "subscribe"


class AuditLoggerAdapter:
    """
    Bridge between Brad's A2AAuditLogger and the SDK's AuditLogger interface.

    Allows using the A2AAuditLogger with OpenClawA2AClient while maintaining
    Brad's event-specific log format and daily rolling files.

    Usage:
        from openclawa2a.a2a_audit import A2AAuditLogger, AuditLoggerAdapter

        a2a_logger = A2AAuditLogger(log_dir="audit/logs")
        adapter = AuditLoggerAdapter(a2a_logger)
        client = OpenClawA2AClient(url, audit_logger=adapter)

        # Or use directly:
        adapter.log("send_message", task_id="123", agent_id="dexter", status="success")
        with adapter.trace("get_task", task_id="123") as span:
            ...
    """

    def __init__(
        self,
        a2a_logger: A2AAuditLogger,
        service_name: str = "openclawa2a",
    ) -> None:
        self._logger = a2a_logger
        self.service_name = service_name

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
        SDK-compatible log() that delegates to A2AAuditLogger.

        Maps SDK operations to A2A event types:
            send_message   → message_sent
            get_task       → task_updated (completed/failed)
            list_tasks     → task_updated
            cancel_task    → task_updated (canceled)
            get_agent_card → agent_discovered
        """
        op = operation if isinstance(operation, str) else operation.value

        if op == "send_message":
            event_type = A2AAuditLogger.EVENT_MESSAGE_SENT
            content = f"send_message trace={trace_id}"
        elif op == "get_task":
            event_type = A2AAuditLogger.EVENT_TASK_UPDATED
            content = f"get_task {task_id} → {status}"
        elif op == "list_tasks":
            event_type = A2AAuditLogger.EVENT_TASK_UPDATED
            content = f"list_tasks context={context_id}"
        elif op == "cancel_task":
            event_type = A2AAuditLogger.EVENT_TASK_UPDATED
            content = f"cancel_task {task_id}"
        elif op == "get_agent_card":
            event_type = A2AAuditLogger.EVENT_AGENT_DISCOVERED
            content = "agent_card fetched"
        elif op == "stream_events":
            event_type = A2AAuditLogger.EVENT_MESSAGE_SENT
            content = f"stream_events {task_id}"
        else:
            event_type = A2AAuditLogger.EVENT_MESSAGE_SENT
            content = op

        source = agent_id or "client"
        target = "agent"

        meta: dict[str, Any] = dict(metadata or {})
        if trace_id:
            meta["trace_id"] = trace_id
        if context_id:
            meta["context_id"] = context_id
        if error:
            meta["error"] = error
        if request_id:
            meta["request_id"] = request_id

        entry = self._logger.log(
            event_type=event_type,
            source=source,
            target=target,
            task_id=task_id,
            content=content,
            status=status,
            metadata=meta if meta else None,
        )
        return trace_id or entry.get("task_id", str(uuid4()))

    def trace(
        self,
        operation: AuditOperation | str,
        *,
        trace_id: Optional[str] = None,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        **metadata: Any,
    ) -> "_A2ASpan":
        """Context manager for tracing operations."""
        return _A2ASpan(
            adapter=self,
            operation=operation,
            trace_id=trace_id,
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


class _A2ASpan:
    """Context manager span for tracing operations with AuditLoggerAdapter."""

    def __init__(
        self,
        adapter: AuditLoggerAdapter,
        operation: AuditOperation | str,
        trace_id: Optional[str],
        task_id: Optional[str],
        context_id: Optional[str],
        metadata: dict,
    ) -> None:
        self.adapter = adapter
        self.operation = operation
        self.trace_id = trace_id or str(uuid4())
        self.task_id = task_id
        self.context_id = context_id
        self.metadata = metadata

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.adapter.log(
                self.operation,
                trace_id=self.trace_id,
                task_id=self.task_id,
                context_id=self.context_id,
                status="failed",
                metadata={**self.metadata, "error": str(exc_val)},
            )
        return False

    def success(self, **kwargs) -> None:
        """Mark the span as successful."""
        self.adapter.log(
            self.operation,
            trace_id=self.trace_id,
            task_id=self.task_id,
            context_id=self.context_id,
            status="completed",
            metadata={**self.metadata, **kwargs},
        )
