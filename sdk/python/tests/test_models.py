"""Tests for openclawa2a.models"""

import pytest
from datetime import datetime

from openclawa2a.models import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Artifact,
    GetTaskRequest,
    ListTasksRequest,
    Message,
    Part,
    PartType,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    StreamEventType,
    StreamResponse,
    Task,
    TaskState,
    TaskStatus,
)


class TestPart:
    def test_text_part(self):
        p = Part(kind=PartType.TEXT, text="Hello world")
        assert p.text == "Hello world"
        assert p.as_text() == "Hello world"

    def test_data_part(self):
        p = Part(kind=PartType.DATA, data={"key": "value"})
        assert p.as_text() == '{"key": "value"}'

    def test_url_part(self):
        p = Part(kind=PartType.URL, url="https://example.com/file.pdf")
        assert "example.com" in p.as_text()


class TestMessage:
    def test_basic_message(self):
        msg = Message(
            role=Role.USER,
            parts=[Part(kind=PartType.TEXT, text="Hello")],
        )
        assert msg.role == Role.USER
        assert len(msg.parts) == 1
        assert msg.as_text() == "Hello"

    def test_message_with_id(self):
        msg = Message(
            role=Role.AGENT,
            parts=[Part(kind=PartType.TEXT, text="Hi there")],
            message_id="msg-123",
        )
        assert msg.message_id == "msg-123"


class TestTaskStatus:
    def test_terminal_states(self):
        for state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED]:
            s = TaskStatus(state=state)
            assert s.is_terminal() is True

    def test_non_terminal_states(self):
        for state in [TaskState.SUBMITTED, TaskState.WORKING, TaskState.INPUT_REQUIRED]:
            s = TaskStatus(state=state)
            assert s.is_terminal() is False


class TestTask:
    def test_mark_working(self):
        task = Task(
            id="t1",
            context_id="c1",
            status=TaskStatus(state=TaskState.SUBMITTED),
        )
        task.mark_working()
        assert task.status.state == TaskState.WORKING

    def test_mark_completed(self):
        task = Task(id="t1", context_id="c1", status=TaskStatus(state=TaskState.WORKING))
        task.mark_completed("Done")
        assert task.status.state == TaskState.COMPLETED
        assert task.status.message == "Done"

    def test_mark_failed(self):
        task = Task(id="t1", context_id="c1", status=TaskStatus(state=TaskState.WORKING))
        task.mark_failed("Error")
        assert task.status.state == TaskState.FAILED
        assert task.status.message == "Error"

    def test_task_artifacts(self):
        task = Task(
            id="t1",
            context_id="c1",
            status=TaskStatus(state=TaskState.SUBMITTED),
            artifacts=[
                Artifact(parts=[Part(kind=PartType.TEXT, text="result")])
            ],
        )
        assert len(task.artifacts) == 1


class TestAgentSkill:
    def test_basic_skill(self):
        skill = AgentSkill(
            id="openclaw:code",
            name="Code Assistant",
            description="Helps write code",
            tags=["coding", "python"],
        )
        assert skill.name == "Code Assistant"
        assert "coding" in skill.tags


class TestAgentCapabilities:
    def test_defaults(self):
        caps = AgentCapabilities()
        assert caps.streaming is True
        assert caps.push_notifications is False
        assert caps.state_transition_history is False

    def test_with_alias(self):
        caps = AgentCapabilities(streaming=True)
        assert caps.streaming is True


class TestAgentCard:
    def test_basic_card(self):
        provider = AgentProvider(organization="myorg", name="my-agent")
        card = AgentCard(
            name="My Agent",
            version="1.0.0",
            description="A test agent",
            provider=provider,
        )
        assert card.agent_id == "myorg/my-agent"

    def test_card_skills(self):
        provider = AgentProvider(organization="myorg")
        skill = AgentSkill(id="s1", name="Test", description="desc")
        card = AgentCard(
            name="A",
            version="1.0",
            description="D",
            provider=provider,
            skills=[skill],
        )
        assert len(card.skills) == 1


class TestSendMessageRequest:
    def test_basic_request(self):
        msg = Message(role=Role.USER, parts=[Part(kind=PartType.TEXT, text="Hi")])
        req = SendMessageRequest(message=msg)
        assert req.message.role == Role.USER
        assert req.stream is False

    def test_request_stream_flag(self):
        msg = Message(role=Role.USER, parts=[Part(kind=PartType.TEXT, text="Hi")])
        req = SendMessageRequest(message=msg, stream=True)
        assert req.stream is True


class TestGetTaskRequest:
    def test_aliases(self):
        req = GetTaskRequest(taskId="t123", historyLength=50)
        assert req.task_id == "t123"
        assert req.history_length == 50


class TestListTasksRequest:
    def test_defaults(self):
        req = ListTasksRequest(contextId="c1")
        assert req.limit == 20
        assert req.marker is None


class TestStreamResponse:
    def test_connected_event(self):
        event = StreamResponse(type=StreamEventType.CONNECTED, heartbeat=True)
        assert event.type == StreamEventType.CONNECTED
        assert event.heartbeat is True

    def test_status_update(self):
        status = TaskStatus(state=TaskState.WORKING)
        event = StreamResponse(type=StreamEventType.STATUS_UPDATE, status=status)
        assert event.status is not None
        assert event.status.state == TaskState.WORKING
