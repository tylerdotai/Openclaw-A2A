"""
OpenClaw A2A — A2A Client

Full-featured A2A client with httpx, streaming, retries, and timeouts.
Thread-safe for concurrent use.
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Iterator,
    Optional,
    TypeVar,
)

import httpx

from openclawa2a.agent_card import AgentCardBuilder
from openclawa2a.audit import AuditLogger, get_audit_logger
from openclawa2a.exceptions import (
    APIKeyError,
    ConnectionError,
    InvalidRequestError,
    OpenClawA2AError,
    ServerError,
    StreamingError,
    TaskNotFoundError,
    TimeoutError,
)
from openclawa2a.models import (
    AgentCard,
    CancelTaskRequest,
    CancelTaskResponse,
    GetTaskRequest,
    ListTasksRequest,
    ListTasksResponse,
    SendMessageRequest,
    SendMessageResponse,
    StreamResponse,
    Task,
    TaskState,
    Message,
    Role,
    Part,
    PartType,
)
from openclawa2a.tracing import inject_trace_headers, new_trace_id, set_current_trace

logger = logging.getLogger(__name__)

T = TypeVar("T")


class OpenClawA2AClient:
    """
    A2A client for communicating with remote agents.

    Supports:
    - Streaming and non-streaming message sending
    - Task management (get, list, cancel, subscribe)
    - Automatic Agent Card discovery
    - Configurable retries, timeouts, and auth
    - Full audit trail via AuditLogger
    - Distributed trace context propagation

    Usage:
        client = OpenClawA2AClient("https://agent.example.com/a2a")
        card = client.get_agent_card()
        task = client.send_message(message={"role": "user", "parts": [{"text": "Hello"}]})
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        retry_multiplier: float = 2.0,
        max_retry_delay: float = 10.0,
        user_agent: str = "openclawa2a/0.1.0",
        audit_logger: Optional[AuditLogger] = None,
        enable_tracing: bool = True,
        follow_redirects: bool = True,
        httpx_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """
        Args:
            base_url: Base URL of the A2A server (with or without trailing slash).
            api_key: Optional API key for authentication.
            timeout: Default request timeout in seconds.
            max_retries: Maximum number of retries on transient errors.
            retry_delay: Initial delay between retries (seconds).
            retry_multiplier: Multiply delay by this each retry.
            max_retry_delay: Cap on retry delay.
            user_agent: User-Agent string for HTTP requests.
            audit_logger: Optional audit logger; uses global if not provided.
            enable_tracing: Inject trace context into outgoing requests.
            follow_redirects: Follow HTTP redirects.
            httpx_client: Optional pre-configured httpx.AsyncClient for reuse.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_multiplier = retry_multiplier
        self.max_retry_delay = max_retry_delay
        self.user_agent = user_agent
        self.audit_logger = audit_logger or get_audit_logger()
        self.enable_tracing = enable_tracing
        self.follow_redirects = follow_redirects
        self._httpx_client = httpx_client
        self._owns_httpx_client = httpx_client is None
        self._executor = ThreadPoolExecutor(max_workers=4)

    # ── HTTP Client ─────────────────────────────────────────────────────────────

    def _default_headers(self, trace_id: Optional[str] = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.enable_tracing:
            trace_headers = inject_trace_headers(trace_id)
            headers.update(trace_headers)
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=self.follow_redirects,
            )
        return self._httpx_client

    async def _close_client(self) -> None:
        if self._owns_httpx_client and self._httpx_client is not None:
            await self._httpx_client.aclose()
            self._httpx_client = None

    # ── Retry Logic ─────────────────────────────────────────────────────────────

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json_data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        stream: bool = False,
    ) -> httpx.Response:
        """
        Execute an HTTP request with exponential backoff retry.
        Retries 429 (rate limit) and 5xx errors.
        """
        trace_id = new_trace_id()
        headers = headers or self._default_headers(trace_id)

        client = await self._get_client()
        url = f"{self.base_url}{path}"
        delay = self.retry_delay

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    headers=headers,
                    timeout=httpx.Timeout(self.timeout),
                    follow_redirects=self.follow_redirects,
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = ServerError(
                        status_code=response.status_code,
                        message=f"Transient server error on {method} {path}",
                    )
                    if attempt < self.max_retries:
                        logger.warning(
                            "Retry %s/%s for %s %s (status %s), sleeping %.1fs",
                            attempt + 1,
                            self.max_retries,
                            method,
                            path,
                            response.status_code,
                            delay,
                        )
                        await self._sleep(delay)
                        delay = min(delay * self.retry_multiplier, self.max_retry_delay)
                        continue
                elif response.status_code == 401 or response.status_code == 403:
                    raise APIKeyError(f"Authentication failed: {response.status_code}")
                elif response.status_code == 404:
                    raise OpenClawA2AError(
                        f"Endpoint not found: {path}",
                        code="NOT_FOUND",
                    )
                elif response.status_code >= 400:
                    try:
                        err_body = response.json()
                    except Exception:
                        err_body = {}
                    raise InvalidRequestError(
                        err_body.get("message", response.text[:200]),
                        details=err_body,
                    )

                return response

            except (ConnectionError, TimeoutError) as e:
                last_error = e
                if attempt < self.max_retries:
                    await self._sleep(delay)
                    delay = min(delay * self.retry_multiplier, self.max_retry_delay)
                    continue
                raise

        # All retries exhausted
        raise ServerError(
            status_code=503,
            message=f"All {self.max_retries} retries failed for {method} {path}",
            details={"last_error": str(last_error)},
        )

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """Async sleep — overrideable for testing."""
        import asyncio

        await asyncio.sleep(seconds)

    # ── Agent Card ───────────────────────────────────────────────────────────────

    async def get_agent_card(self) -> AgentCard:
        """
        Fetch the remote agent's Agent Card.

        This is the A2A discovery endpoint.
        """
        trace_id = new_trace_id()
        with self.audit_logger.trace("get_agent_card", trace_id=trace_id):
            response = await self._request_with_retry(
                "GET",
                "/agent-card",
                headers=self._default_headers(trace_id),
            )

            if response.headers.get("content-type", "").startswith("text/event-stream"):
                raise OpenClawA2AError(
                    "Agent Card endpoint returned SSE stream; expected JSON",
                    code="UNEXPECTED_CONTENT_TYPE",
                )

            data = response.json()
            card = AgentCard.model_validate(data)

            self.audit_logger.log(
                "get_agent_card",
                trace_id=trace_id,
                agent_id=card.agent_id,
                status="success",
                metadata={"agent_name": card.name, "version": card.version},
            )
            return card

    # ── Messaging ────────────────────────────────────────────────────────────────

    async def send_message(
        self,
        message: dict[str, Any] | Message,
        *,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        stream: bool = False,
        trace_id: Optional[str] = None,
    ) -> SendMessageResponse:
        """
        Send a message to the agent and get a task response.

        Args:
            message: Message dict or Message object with role and parts.
            task_id: Optional existing task to continue.
            context_id: Context grouping ID.
            stream: If True, returns an async iterator for SSE.
            trace_id: Optional trace context.

        Returns:
            SendMessageResponse with task and optional result message.
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        # Normalize message to dict
        if isinstance(message, Message):
            msg_dict = message.model_dump(by_alias=True, exclude_none=True)
        else:
            msg_dict = dict(message)

        # Ensure required fields
        if "role" not in msg_dict:
            msg_dict["role"] = "user"
        if "parts" not in msg_dict:
            msg_dict["parts"] = [{"kind": "text", "text": str(msg_dict.get("text", ""))}]

        request = SendMessageRequest(
            message=Message.model_validate(msg_dict),
            task_id=task_id,
            context_id=context_id,
            stream=stream,
        )

        with self.audit_logger.trace(
            "send_message",
            trace_id=trace_id,
            task_id=task_id,
            context_id=context_id,
        ) as span:
            response = await self._request_with_retry(
                "POST",
                "/message:send",
                json_data=request.model_dump(by_alias=True, exclude_none=True),
                headers=self._default_headers(trace_id),
            )

            result = SendMessageResponse.model_validate(response.json())

            span.success(task_id=result.task.id, context_id=result.task.context_id)

            return result

    async def send_message_streaming(
        self,
        message: dict[str, Any] | Message,
        *,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[StreamResponse]:
        """
        Send a message and stream SSE responses.

        Yields StreamResponse events as they arrive.

        Usage:
            async for event in client.send_message_streaming(message={...}):
                print(event.type, event.message)
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        if isinstance(message, Message):
            msg_dict = message.model_dump(by_alias=True, exclude_none=True)
        else:
            msg_dict = dict(message)

        if "role" not in msg_dict:
            msg_dict["role"] = "user"
        if "parts" not in msg_dict:
            msg_dict["parts"] = [{"kind": "text", "text": str(msg_dict.get("text", ""))}]

        request = SendMessageRequest(
            message=Message.model_validate(msg_dict),
            task_id=task_id,
            context_id=context_id,
            stream=True,
        )

        headers = self._default_headers(trace_id)
        headers["Accept"] = "text/event-stream"

        with self.audit_logger.trace(
            "stream_message",
            trace_id=trace_id,
            task_id=task_id,
            context_id=context_id,
        ) as span:
            client = await self._get_client()
            url = f"{self.base_url}/message:send"

            try:
                async with client.stream(
                    "POST",
                    url,
                    json=request.model_dump(by_alias=True, exclude_none=True),
                    headers=headers,
                    timeout=httpx.Timeout(self.timeout),
                ) as response:
                    if response.status_code == 401 or response.status_code == 403:
                        raise APIKeyError(f"Authentication failed: {response.status_code}")
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ServerError(
                            status_code=response.status_code,
                            message=body.decode(errors="replace")[:500],
                        )

                    async for line in response.aiter_lines():
                        if not line.strip() or line.startswith("#"):
                            continue
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                import json as _json

                                event_data = _json.loads(data)
                                event = StreamResponse.model_validate(event_data)
                                yield event
                            except Exception as e:
                                logger.warning("Failed to parse SSE event: %s", e)
                                continue

                    span.success()

            except Exception as e:
                span.failure(error_code="STREAMING_ERROR", error_message=str(e))
                raise StreamingError(f"Streaming request failed: {e}") from e

    # ── Task Management ─────────────────────────────────────────────────────────

    async def get_task(
        self,
        task_id: str,
        *,
        history_length: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> Task:
        """
        Retrieve a task by ID.
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        request = GetTaskRequest(taskId=task_id, historyLength=history_length)

        with self.audit_logger.trace(
            "get_task",
            trace_id=trace_id,
            task_id=task_id,
        ):
            response = await self._request_with_retry(
                "GET",
                f"/tasks/{task_id}",
                headers=self._default_headers(trace_id),
            )

            if response.status_code == 404:
                raise TaskNotFoundError(task_id)

            task = Task.model_validate(response.json())
            return task

    async def list_tasks(
        self,
        context_id: str,
        *,
        limit: int = 20,
        marker: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> ListTasksResponse:
        """
        List tasks for a context.
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        request = ListTasksRequest(contextId=context_id, limit=limit, marker=marker)

        with self.audit_logger.trace(
            "list_tasks",
            trace_id=trace_id,
            context_id=context_id,
        ):
            response = await self._request_with_retry(
                "GET",
                f"/tasks?context_id={context_id}&limit={limit}"
                + (f"&marker={marker}" if marker else ""),
                headers=self._default_headers(trace_id),
            )

            return ListTasksResponse.model_validate(response.json())

    async def cancel_task(
        self,
        task_id: str,
        *,
        trace_id: Optional[str] = None,
    ) -> CancelTaskResponse:
        """
        Cancel a running task.
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        request = CancelTaskRequest(taskId=task_id)

        with self.audit_logger.trace(
            "cancel_task",
            trace_id=trace_id,
            task_id=task_id,
        ) as span:
            response = await self._request_with_retry(
                "POST",
                f"/tasks/{task_id}:cancel",
                json_data=request.model_dump(by_alias=True, exclude_none=True),
                headers=self._default_headers(trace_id),
            )

            if response.status_code == 404:
                raise TaskNotFoundError(task_id)

            result = CancelTaskResponse.model_validate(response.json())
            span.success(canceled=result.canceled)
            return result

    # ── SSE Subscribe ───────────────────────────────────────────────────────────

    async def subscribe_to_task(
        self,
        task_id: str,
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[StreamResponse]:
        """
        Subscribe to live task updates via SSE.

        Keeps the connection open and yields status/artifact updates.
        """
        trace_id = trace_id or new_trace_id()
        set_current_trace(trace_id)

        headers = self._default_headers(trace_id)
        headers["Accept"] = "text/event-stream"

        with self.audit_logger.trace(
            "subscribe_task",
            trace_id=trace_id,
            task_id=task_id,
        ):
            client = await self._get_client()
            url = f"{self.base_url}/tasks/{task_id}:subscribe"

            try:
                async with client.stream(
                    "GET",
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(self.timeout),
                ) as response:
                    if response.status_code == 404:
                        raise TaskNotFoundError(task_id)
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ServerError(
                            status_code=response.status_code,
                            message=body.decode(errors="replace")[:500],
                        )

                    async for line in response.aiter_lines():
                        if not line.strip() or line.startswith("#"):
                            continue
                        if line.startswith("data:"):
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                import json as _json

                                event_data = _json.loads(data)
                                yield StreamResponse.model_validate(event_data)
                            except Exception as e:
                                logger.warning("Failed to parse SSE event: %s", e)
                                continue

            except Exception as e:
                raise StreamingError(f"Subscribe failed for task {task_id}: {e}") from e

    # ── Lifecycle ────────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._close_client()
        self._executor.shutdown(wait=False)

    def __repr__(self) -> str:
        return f"OpenClawA2AClient(base_url={self.base_url!r})"
