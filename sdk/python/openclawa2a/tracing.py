"""
OpenClaw A2A — Distributed Tracing

OpenTelemetry-compatible trace context propagation.
Trace IDs flow through A2A headers so entire request chains
can be assembled from logs.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from openclawa2a.exceptions import TraceError

logger = logging.getLogger(__name__)

# ── Trace ID ──────────────────────────────────────────────────────────────────


def new_trace_id() -> str:
    """Generate a new trace ID (32-char hex, similar to W3C TraceContext)."""
    return uuid.uuid4().hex


# ── Context Variable (process-global trace state) ────────────────────────────

_current_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_current_trace_flags: ContextVar[Optional[str]] = ContextVar("trace_flags", default=None)


def get_current_trace_id() -> Optional[str]:
    return _current_trace_id.get()


def get_current_span_id() -> Optional[str]:
    return _current_span_id.get()


def set_current_trace(
    trace_id: str,
    span_id: Optional[str] = None,
    trace_flags: str = "01",
) -> None:
    _current_trace_id.set(trace_id)
    if span_id is not None:
        _current_span_id.set(span_id)
    _current_trace_flags.set(trace_flags)


def clear_current_trace() -> None:
    """Reset all trace context vars to their default (None)."""
    _current_trace_id.set(None)
    _current_span_id.set(None)
    _current_trace_flags.set(None)


# ── A2A Trace Headers ─────────────────────────────────────────────────────────
# These mirror W3C TraceContext fields used by OpenTelemetry.

TRACE_PARENT_HEADER = "traceparent"
TRACE_STATE_HEADER = "tracestate"


def build_traceparent(trace_id: str, span_id: str, flags: str = "01") -> str:
    """
    Build a W3C traceparent header value.

    Format: 00-{trace_id}-{span_id}-{flags}
    Example: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
    """
    if len(trace_id) != 32:
        raise TraceError(f"trace_id must be 32 hex chars, got {len(trace_id)}")
    if len(span_id) != 16:
        raise TraceError(f"span_id must be 16 hex chars, got {len(span_id)}")
    return f"00-{trace_id}-{span_id}-{flags}"


def parse_traceparent(value: str) -> dict[str, str]:
    """Parse a W3C traceparent header value."""
    parts = value.split("-")
    if len(parts) != 4 or parts[0] != "00":
        raise TraceError(f"Invalid traceparent format: {value!r}")
    _, trace_id, span_id, flags = parts
    if len(trace_id) != 32 or len(span_id) != 16:
        raise TraceError(f"Invalid traceparent lengths: {value!r}")
    return {"trace_id": trace_id, "span_id": span_id, "flags": flags}


def inject_trace_headers(trace_id: Optional[str] = None) -> dict[str, str]:
    """
    Return headers dict with trace context for outgoing HTTP requests.

    If trace_id is None, generates a new one.
    Span ID is always freshly generated per request.
    """
    tid = trace_id or new_trace_id()
    span = uuid.uuid4().hex[:16]
    return {
        TRACE_PARENT_HEADER: build_traceparent(tid, span),
        TRACE_STATE_HEADER: "openclawa2a=1",
    }


def extract_trace_headers(headers: dict[str, str]) -> dict[str, Any]:
    """
    Extract trace context from received HTTP headers.

    Returns a dict with trace_id, span_id, flags, or empty dict if missing.
    """
    parent = headers.get(TRACE_PARENT_HEADER.lower()) or headers.get(TRACE_PARENT_HEADER, "")
    if not parent:
        return {}
    try:
        parsed = parse_traceparent(parent)
        return {
            "trace_id": parsed["trace_id"],
            "span_id": parsed["span_id"],
            "flags": parsed["flags"],
        }
    except TraceError:
        logger.warning("Could not parse traceparent: %r", parent)
        return {}


# ── Tracer wrapper ────────────────────────────────────────────────────────────

_tracer_config: dict[str, Any] = {"service_name": "openclawa2a", "enabled": False}


def setup_tracing(
    service_name: str = "openclawa2a",
    enabled: bool = False,
    exporter: Optional[Any] = None,
) -> None:
    """
    Configure the global tracer.

    Args:
        service_name: Service name for trace spans.
        enabled: If True, activate OpenTelemetry tracing.
        exporter: Optional OTLP exporter (not used unless enabled=True).
    """
    _tracer_config["service_name"] = service_name
    _tracer_config["enabled"] = enabled
    _tracer_config["exporter"] = exporter
    logger.info("Tracing configured: service=%s enabled=%s", service_name, enabled)


def get_tracer() -> _Tracer:
    """Get a tracer instance."""
    return _Tracer(name=_tracer_config.get("service_name", "openclawa2a"))


class _Tracer:
    """Lightweight tracer that mimics OpenTelemetry's span lifecycle."""

    def __init__(self, name: str) -> None:
        self.name = name

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> "_Span":
        return _Span(
            name=name,
            trace_id=trace_id or get_current_trace_id() or new_trace_id(),
            parent_id=parent_id,
            service_name=self.name,
        )


class _Span:
    """A single trace span."""

    def __init__(
        self,
        name: str,
        trace_id: str,
        parent_id: Optional[str],
        service_name: str,
    ) -> None:
        self.name = name
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.service_name = service_name
        self.span_id = uuid.uuid4().hex[:16]
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.tags: dict[str, Any] = {}

    def set_tag(self, key: str, value: Any) -> None:
        self.tags[key] = value

    def set_tags(self, tags: dict[str, Any]) -> None:
        self.tags.update(tags)

    def end(self) -> None:
        self.end_time = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "service": self.service_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "tags": self.tags,
        }
