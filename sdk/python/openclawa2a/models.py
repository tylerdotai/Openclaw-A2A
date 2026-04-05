"""
OpenClaw A2A — Pydantic v2 Data Models

Implements the A2A protocol schema with full type safety.
All models are backward-compatible and validation-first.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


class TaskState(str, Enum):
    """Task lifecycle states."""

    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INPUT_REQUIRED = "input-required"


class Role(str, Enum):
    """Message sender role."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class PartType(str, Enum):
    """Content part type."""

    TEXT = "text"
    DATA = "data"
    RAW = "raw"
    URL = "url"


class StreamEventType(str, Enum):
    """SSE stream event types."""

    MESSAGE = "message"
    STATUS_UPDATE = "status_update"
    ARTIFACT_UPDATE = "artifact_update"
    ERROR = "error"
    CONNECTED = "connected"
    HEARTBEAT = "heartbeat"


# ── Task ───────────────────────────────────────────────────────────────────────


class TaskStatus(BaseModel):
    """Current task status with state and optional message."""

    model_config = ConfigDict(use_enum_values=True)

    state: TaskState
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())

    def is_terminal(self) -> bool:
        return self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED)


class Task(BaseModel):
    """An A2A task — the core protocol unit."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique task identifier")
    context_id: str = Field(..., description="Groups related tasks")
    status: TaskStatus
    session_id: Optional[str] = Field(default=None, description="Optional session grouping")
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    artifacts: list[Artifact] = Field(default_factory=list)
    history: list[Message] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_working(self, message: Optional[str] = None) -> None:
        self.status = TaskStatus(state=TaskState.WORKING, message=message)
        self.updated_at = datetime.now()

    def mark_completed(self, message: Optional[str] = None) -> None:
        self.status = TaskStatus(state=TaskState.COMPLETED, message=message)
        self.updated_at = datetime.now()

    def mark_failed(self, message: Optional[str] = None) -> None:
        self.status = TaskStatus(state=TaskState.FAILED, message=message)
        self.updated_at = datetime.now()

    def mark_canceled(self, message: Optional[str] = None) -> None:
        self.status = TaskStatus(state=TaskState.CANCELED, message=message)
        self.updated_at = datetime.now()


# ── Message / Part ─────────────────────────────────────────────────────────────


class Part(BaseModel):
    """A message content part — text, data, raw bytes, or URL."""

    model_config = ConfigDict(populate_by_name=True)

    kind: PartType = Field(..., alias="kind")
    text: Optional[str] = Field(default=None, max_length=100000)
    data: Optional[dict[str, Any]] = Field(default=None)
    raw: Optional[bytes] = Field(default=None, exclude=True)  # Never serialized to JSON
    url: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 2000:
            raise ValueError("URL must be <= 2000 characters")
        return v

    def as_text(self) -> str:
        if self.kind == PartType.TEXT:
            return self.text or ""
        if self.kind == PartType.DATA:
            import json

            return json.dumps(self.data, default=str)
        return str(self.url or "")


class Message(BaseModel):
    """An A2A message from USER or AGENT."""

    model_config = ConfigDict(populate_by_name=True)

    role: Role = Field(..., description="Sender role")
    parts: list[Part] = Field(..., min_length=1, description="Content parts")
    message_id: Optional[str] = Field(default=None, alias="messageId")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    reference_task_ids: list[str] = Field(default_factory=list, alias="referenceTaskIds")

    def as_text(self) -> str:
        return " ".join(p.as_text() for p in self.parts)


# ── Artifact ──────────────────────────────────────────────────────────────────


class Artifact(BaseModel):
    """Output artifact from a task."""

    model_config = ConfigDict(populate_by_name=True)

    artifact_id: Optional[str] = Field(default=None, alias="artifactId")
    name: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    parts: list[Part] = Field(...)
    index: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now())


# ── Agent Card ────────────────────────────────────────────────────────────────


class AgentSkill(BaseModel):
    """A capability/skill exposed by an agent."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=2000)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCapabilities(BaseModel):
    """What this agent supports."""

    model_config = ConfigDict(populate_by_name=True)

    streaming: bool = Field(default=True, alias="streaming")
    push_notifications: bool = Field(default=False, alias="pushNotifications")
    state_transition_history: bool = Field(default=False, alias="stateTransitionHistory")
    extensions: list[str] = Field(default_factory=list)


class AgentProvider(BaseModel):
    """Who/what provides this agent."""

    model_config = ConfigDict(populate_by_name=True)

    organization: str = Field(..., alias="organization")
    name: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    version: Optional[str] = Field(default=None)


class AgentInterface(BaseModel):
    """Protocol binding for this agent."""

    model_config = ConfigDict(populate_by_name=True)

    protocol: str = Field(default="http://a2a-protocol.org")
    version: str = Field(default="1.0.0")


class AgentCard(BaseModel):
    """Agent Card — the A2A discovery manifest."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=200)
    version: str = Field(..., max_length=50)
    description: str = Field(..., max_length=5000)
    provider: AgentProvider
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = Field(default_factory=list)
    interfaces: list[AgentInterface] = Field(
        default_factory=lambda: [AgentInterface()],
    )
    url: Optional[str] = Field(default=None, max_length=2000)
    authentication: dict[str, Any] = Field(default_factory=dict)
    default_api_key: Optional[str] = Field(default=None, exclude=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        return f"{self.provider.organization}/{self.name}"


# ── Requests / Responses ──────────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    """Request to send a message and create/get a task."""

    model_config = ConfigDict(populate_by_name=True)

    message: Message = Field(..., description="The message to send")
    task_id: Optional[str] = Field(default=None, description="Existing task ID to continue")
    context_id: Optional[str] = Field(default=None, description="Context grouping ID")
    stream: bool = Field(default=False)
    push_notification_url: Optional[str] = Field(
        default=None,
        alias="pushNotificationUrl",
    )


class SendMessageResponse(BaseModel):
    """Response to send_message."""

    model_config = ConfigDict(populate_by_name=True)

    task: Task
    result: Optional[Message] = Field(default=None, description="Final response message if non-streaming")


class GetTaskRequest(BaseModel):
    """Request to retrieve a task by ID."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    history_length: Optional[int] = Field(default=None, ge=0, le=1000, alias="historyLength")


class ListTasksRequest(BaseModel):
    """Request to list tasks for a context."""

    model_config = ConfigDict(populate_by_name=True)

    context_id: str = Field(..., alias="contextId")
    limit: int = Field(default=20, ge=1, le=100)
    marker: Optional[str] = None


class ListTasksResponse(BaseModel):
    """Response with task list."""

    model_config = ConfigDict(populate_by_name=True)

    tasks: list[Task]
    next_marker: Optional[str] = Field(default=None, alias="nextMarker")


class CancelTaskRequest(BaseModel):
    """Request to cancel a running task."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")


class CancelTaskResponse(BaseModel):
    """Response after canceling a task."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str
    canceled: bool


class SubscribeRequest(BaseModel):
    """Subscribe to live task updates via SSE."""

    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")


# ── Streaming ─────────────────────────────────────────────────────────────────


class StreamResponse(BaseModel):
    """A single SSE event from a streaming response."""

    model_config = ConfigDict(populate_by_name=True)

    type: StreamEventType
    task_id: Optional[str] = Field(default=None, alias="taskId")
    status: Optional[TaskStatus] = None
    message: Optional[Message] = None
    artifact: Optional[Artifact] = None
    error: Optional[str] = None
    heartbeat: Optional[bool] = None
