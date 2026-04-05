"""
OpenClaw A2A — A2A Server Base

Base server class for building A2A-compliant agents.
Provides route handlers, SSE streaming, and task state management.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Optional

from openclawa2a.agent_card import AgentCard, AgentCardBuilder
from openclawa2a.audit import AuditLogger, get_audit_logger
from openclawa2a.exceptions import (
    InvalidRequestError,
    OpenClawA2AError,
    TaskNotFoundError,
)
from openclawa2a.models import (
    Artifact,
    Message,
    Part,
    PartType,
    SendMessageRequest,
    SendMessageResponse,
    StreamEventType,
    StreamResponse,
    Task,
    TaskState,
    TaskStatus,
)
from openclawa2a.tracing import (
    extract_trace_headers,
    inject_trace_headers,
    new_trace_id,
    set_current_trace,
)

logger = logging.getLogger(__name__)


# ── Route Handler Types ───────────────────────────────────────────────────────


RoutedHandler = Callable[[dict[str, Any], dict[str, str]], Any]


class A2AServer(ABC):
    """
    Base class for A2A servers.

    Subclass it and implement the message handler to build
    a full A2A-compliant agent.

    Usage:
        class MyAgent(A2AServer):
            async def handle_message(self, message: Message, context: dict) -> Message:
                return Message(role="agent", parts=[Part(kind="text", text="Hello!")])

        server = MyAgent(agent_card=card)
        await server.start()
    """

    def __init__(
        self,
        agent_card: Optional[AgentCard] = None,
        agent_card_builder: Optional[AgentCardBuilder] = None,
        audit_logger: Optional[AuditLogger] = None,
        enable_tracing: bool = True,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        """
        Args:
            agent_card: The A2A Agent Card. Auto-built if not provided.
            agent_card_builder: Builder for auto-generating agent card.
            audit_logger: Audit logger instance.
            enable_tracing: Enable distributed tracing.
            host: Host to bind to.
            port: Port to bind to.
        """
        self.agent_card = agent_card or (agent_card_builder or AgentCardBuilder()).build()
        self.audit_logger = audit_logger or get_audit_logger()
        self.enable_tracing = enable_tracing
        self.host = host
        self.port = port

        # In-memory task store (override with persistent storage in production)
        self._tasks: dict[str, Task] = {}
        self._tasks_lock = asyncio.Lock()

        # Active SSE subscriptions: task_id -> list of async queues
        self._subscriptions: dict[str, list[asyncio.Queue[Optional[StreamResponse]]]] = {}

        # HTTP server handle
        self._server: Optional[asyncio.Server] = None

    # ── Task Store ─────────────────────────────────────────────────────────────

    async def _store_task(self, task: Task) -> None:
        async with self._tasks_lock:
            self._tasks[task.id] = task

    async def _get_task(self, task_id: str) -> Optional[Task]:
        async with self._tasks_lock:
            return self._tasks.get(task_id)

    async def _list_tasks(self, context_id: str) -> list[Task]:
        async with self._tasks_lock:
            return [t for t in self._tasks.values() if t.context_id == context_id]

    # ── Abstract Handler ────────────────────────────────────────────────────────

    @abstractmethod
    async def handle_message(
        self,
        message: Message,
        context: dict[str, Any],
    ) -> Message:
        """
        Handle an incoming A2A message and return an agent response.

        Override this in your subclass.

        Args:
            message: The incoming user message.
            context: Request context (trace_id, task_id, context_id, headers).

        Returns:
            The agent's response message.
        """
        ...

    # ── Streaming helpers ──────────────────────────────────────────────────────

    async def _stream_task_events(self, task_id: str) -> AsyncIterator[StreamResponse]:
        """
        Yield SSE events for a task until it reaches a terminal state
        or the subscriber disconnects.
        """
        queue: asyncio.Queue[Optional[StreamResponse]] = asyncio.Queue()
        if task_id not in self._subscriptions:
            self._subscriptions[task_id] = []
        self._subscriptions[task_id].append(queue)

        try:
            yield StreamResponse(
                type=StreamEventType.CONNECTED,
                task_id=task_id,
                heartbeat=True,
            )

            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event

                # Stop on terminal state
                if event.status and event.status.is_terminal():
                    break
        finally:
            if task_id in self._subscriptions:
                try:
                    self._subscriptions[task_id].remove(queue)
                except ValueError:
                    pass

    async def _broadcast(
        self,
        task_id: str,
        event: StreamResponse,
    ) -> None:
        """Broadcast an event to all subscribers of a task."""
        if task_id in self._subscriptions:
            for queue in list(self._subscriptions[task_id]):
                try:
                    await queue.put(event)
                except Exception:
                    pass

    async def _emit_heartbeat(self, task_id: str) -> None:
        """Emit a heartbeat to keep SSE connections alive."""
        await self._broadcast(
            task_id,
            StreamResponse(type=StreamEventType.HEARTBEAT, task_id=task_id, heartbeat=True),
        )

    # ── Route Handlers ─────────────────────────────────────────────────────────

    async def _route_send_message(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        """
        Handle POST /message:send

        Creates a new task or continues an existing one.
        """
        trace_context = {}
        if self.enable_tracing:
            extracted = extract_trace_headers(headers)
            if extracted:
                trace_context = extracted
                set_current_trace(extracted["trace_id"])
            else:
                trace_id = new_trace_id()
                trace_context = {"trace_id": trace_id}
                set_current_trace(trace_id)

        trace_id = trace_context.get("trace_id", new_trace_id())

        with self.audit_logger.trace(
            "receive_message",
            trace_id=trace_id,
        ) as span:
            try:
                request = SendMessageRequest.model_validate(body)
            except Exception as e:
                raise InvalidRequestError(f"Invalid request body: {e}")

            task_id = request.task_id or uuid.uuid4().hex
            context_id = request.context_id or uuid.uuid4().hex

            # Create or get task
            task = await self._get_task(task_id)
            if task is None:
                task = Task(
                    id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.SUBMITTED),
                )
                await self._store_task(task)
                self.audit_logger.log(
                    "task_created",
                    trace_id=trace_id,
                    task_id=task_id,
                    context_id=context_id,
                )

            # Mark working
            task.mark_working()
            await self._store_task(task)

            # Build context for handler
            ctx: dict[str, Any] = {
                **trace_context,
                "task_id": task_id,
                "context_id": context_id,
                "headers": headers,
            }

            # Process message
            try:
                result_message = await self.handle_message(request.message, ctx)

                task.mark_completed("Completed successfully")
                await self._store_task(task)

                # Broadcast completion
                await self._broadcast(
                    task_id,
                    StreamResponse(
                        type=StreamEventType.STATUS_UPDATE,
                        task_id=task_id,
                        status=task.status,
                        message=result_message,
                    ),
                )

                span.success(task_id=task_id)

                return 200, SendMessageResponse(
                    task=task,
                    result=result_message,
                ).model_dump(by_alias=True, exclude_none=True)

            except Exception as e:
                task.mark_failed(str(e)[:500])
                await self._store_task(task)

                await self._broadcast(
                    task_id,
                    StreamResponse(
                        type=StreamEventType.ERROR,
                        task_id=task_id,
                        error=str(e),
                    ),
                )

                span.failure(error_code="HANDLER_ERROR", error_message=str(e))
                raise

    async def _route_get_task(
        self,
        task_id: str,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        """Handle GET /tasks/{task_id}"""
        task = await self._get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return 200, task.model_dump(by_alias=True, exclude_none=True)

    async def _route_list_tasks(
        self,
        query: dict[str, str],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        """Handle GET /tasks?context_id=...&limit=..."""
        context_id = query.get("context_id")
        if not context_id:
            raise InvalidRequestError("context_id is required for list_tasks")
        limit = int(query.get("limit", 20))
        tasks = await self._list_tasks(context_id)
        return 200, {"tasks": [t.model_dump(by_alias=True) for t in tasks[:limit]]}

    async def _route_cancel_task(
        self,
        task_id: str,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        """Handle POST /tasks/{task_id}:cancel"""
        task = await self._get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        task.mark_canceled("Canceled by client")
        await self._store_task(task)

        self.audit_logger.log("task_canceled", task_id=task_id)

        await self._broadcast(
            task_id,
            StreamResponse(
                type=StreamEventType.STATUS_UPDATE,
                task_id=task_id,
                status=task.status,
            ),
        )

        return 200, {"taskId": task_id, "canceled": True}

    async def _route_agent_card(
        self,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        """Handle GET /agent-card"""
        return 200, self.agent_card.model_dump(by_alias=True, exclude_none=True)

    # ── SSE Streaming Route ─────────────────────────────────────────────────────

    async def _route_stream(
        self,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        """
        Handle POST /message:send with stream=True.
        Yields SSE-encoded bytes.
        """
        # First handle the message
        _, response = await self._route_send_message(body, headers)
        task_id = response.get("task", {}).get("id")

        if not task_id:
            yield b"data: {\"type\":\"error\",\"error\":\"no task_id\"}\n\n"
            return

        # Then stream task events
        async for event in self._stream_task_events(task_id):
            yield f"data: {json.dumps(event.model_dump(by_alias=True), default=str)}\n\n".encode()

        yield b"data: [DONE]\n\n"

    async def _route_subscribe(
        self,
        task_id: str,
        headers: dict[str, str],
    ) -> AsyncIterator[bytes]:
        """Handle GET /tasks/{task_id}:subscribe — SSE subscription."""
        task = await self._get_task(task_id)
        if task is None:
            yield b"data: {\"type\":\"error\",\"error\":\"task_not_found\"}\n\n"
            return

        async for event in self._stream_task_events(task_id):
            yield f"data: {json.dumps(event.model_dump(by_alias=True), default=str)}\n\n".encode()

        yield b"data: [DONE]\n\n"

    # ── HTTP Server ─────────────────────────────────────────────────────────────

    async def _handle_request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[dict[str, Any]],
        headers: dict[str, str],
        query: Optional[dict[str, str]] = None,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        """
        Central HTTP request router.

        Returns (status_code, response_body, response_headers).
        """
        status = 200
        response_headers: dict[str, str] = {"Content-Type": "application/json"}

        try:
            # Agent Card
            if method == "GET" and path == "/agent-card":
                status, body_out = await self._route_agent_card(headers)
                return status, body_out, response_headers

            # Tasks
            if method == "GET" and path.startswith("/tasks"):
                if path == "/tasks":
                    status, body_out = await self._route_list_tasks(query or {}, headers)
                    return status, body_out, response_headers
                else:
                    # GET /tasks/{id}
                    task_id = path.split("/")[2].split(":")[0]
                    status, body_out = await self._route_get_task(task_id, headers)
                    return status, body_out, response_headers

            # POST /tasks/{id}:cancel
            if method == "POST" and ":cancel" in path:
                task_id = path.split("/")[2]
                status, body_out = await self._route_cancel_task(task_id, body or {}, headers)
                return status, body_out, response_headers

            # POST /message:send
            if method == "POST" and path == "/message:send":
                status, body_out = await self._route_send_message(body or {}, headers)
                return status, body_out, response_headers

            # Default: 404
            return 404, {"error": "Not found", "path": path}, {"Content-Type": "application/json"}

        except OpenClawA2AError as e:
            return e.code or "SERVER_ERROR", e.to_dict(), {"Content-Type": "application/json"}
        except Exception as e:
            logger.exception("Unhandled server error")
            return 500, {"error": "Internal server error", "message": str(e)[:200]}, {
                "Content-Type": "application/json"
            }

    async def start(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Start the A2A HTTP server."""
        host = host or self.host
        port = port or self.port

        async def handler(
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter,
        ) -> None:
            """Minimal HTTP server handler."""
            try:
                request_line = await reader.readline()
                if not request_line:
                    return

                method, path, _ = request_line.decode().split(" ")

                # Read headers
                headers: dict[str, str] = {}
                content_length = 0
                while True:
                    line = await reader.readline()
                    if line in (b"\r\n", b"\n", b""):
                        break
                    key, _, value = line.decode().partition(": ")
                    headers[key.strip().lower()] = value.strip()
                    if key.strip().lower() == "content-length":
                        content_length = int(value.strip())

                # Read body
                body_bytes = b""
                if content_length > 0:
                    body_bytes = await reader.readexactly(content_length)

                # Parse query string
                query: dict[str, str] = {}
                if "?" in path:
                    path, qs = path.split("?", 1)
                    for param in qs.split("&"):
                        if "=" in param:
                            k, v = param.split("=", 1)
                            query[k] = v

                # Parse body
                body: Optional[dict[str, Any]] = None
                if body_bytes:
                    try:
                        body = json.loads(body_bytes.decode())
                    except json.JSONDecodeError:
                        body = None

                # Determine if SSE response
                accept = headers.get("accept", "")
                is_sse = "text/event-stream" in accept

                status, response_body, response_headers = await self._handle_request(
                    method=method,
                    path=path,
                    body=body,
                    headers=headers,
                    query=query,
                )

                if is_sse and status == 200:
                    response_headers["Content-Type"] = "text/event-stream"
                    response_headers["Cache-Control"] = "no-cache"
                    response_headers["Connection"] = "keep-alive"

                    # SSE response — stream body
                    response_headers_str = "\r\n".join(
                        f"{k}: {v}" for k, v in response_headers.items()
                    )
                    writer.write(f"HTTP/1.1 200 OK\r\n{response_headers_str}\r\n\r\n".encode())
                    await writer.drain()

                    if path == "/message:send" and body:
                        async for chunk in self._route_stream(body, headers):
                            writer.write(chunk)
                            await writer.drain()
                    elif ":subscribe" in path:
                        task_id = path.split("/")[2]
                        async for chunk in self._route_subscribe(task_id, headers):
                            writer.write(chunk)
                            await writer.drain()
                else:
                    # Normal JSON response
                    response_body_str = json.dumps(response_body, default=str)
                    response_headers_str = "\r\n".join(
                        f"{k}: {v}" for k, v in response_headers.items()
                    )
                    body_bytes_out = response_body_str.encode()
                    writer.write(
                        f"HTTP/1.1 {status} OK\r\n"
                        f"{response_headers_str}\r\n"
                        f"Content-Length: {len(body_bytes_out)}\r\n\r\n".encode()
                        + body_bytes_out
                    )
                    await writer.drain()

            except Exception as e:
                logger.exception("Request handler error")
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        self._server = await asyncio.start_server(handler, host, port)
        logger.info("A2A server listening on %s:%s", host, port)

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def __repr__(self) -> str:
        return f"A2AServer(agent={self.agent_card.name!r}, host={self.host}:{self.port})"
