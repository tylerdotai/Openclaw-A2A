"""Tests for openclawa2a.server"""

import pytest
import asyncio

from openclawa2a.models import (
    AgentCard,
    AgentCapabilities,
    AgentInterface,
    AgentProvider,
    Message,
    Part,
    PartType,
    Role,
    Task,
    TaskState,
    TaskStatus,
)
from openclawa2a.server import A2AServer


class EchoAgent(A2AServer):
    """A minimal test agent that echoes messages."""

    async def handle_message(self, message: Message, context: dict) -> Message:
        text = message.as_text()
        return Message(
            role=Role.AGENT,
            parts=[Part(kind=PartType.TEXT, text=f"Echo: {text}")],
        )


class TestA2AServerConstruction:
    def test_basic_construction(self):
        agent = EchoAgent()
        assert agent.agent_card is not None
        assert agent.host == "0.0.0.0"
        assert agent.port == 8080

    def test_with_custom_agent_card(self):
        provider = AgentProvider(organization="testorg")
        card = AgentCard(
            name="TestAgent",
            version="1.0.0",
            description="Test",
            provider=provider,
        )
        agent = EchoAgent(agent_card=card)
        assert agent.agent_card.name == "TestAgent"
        assert agent.agent_card.agent_id == "testorg/testagent"

    def test_repr(self):
        agent = EchoAgent()
        assert "A2AServer" in repr(agent)
        assert "openclaw-agent" in repr(agent)


class TestTaskStore:
    @pytest.mark.asyncio
    async def test_store_and_get_task(self):
        agent = EchoAgent()
        task = Task(
            id="task-1",
            context_id="ctx-1",
            status=TaskStatus(state=TaskState.SUBMITTED),
        )
        await agent._store_task(task)

        retrieved = await agent._get_task("task-1")
        assert retrieved is not None
        assert retrieved.id == "task-1"

    @pytest.mark.asyncio
    async def test_get_missing_task(self):
        agent = EchoAgent()
        result = await agent._get_task("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tasks(self):
        agent = EchoAgent()
        task1 = Task(id="t1", context_id="c1", status=TaskStatus(state=TaskState.SUBMITTED))
        task2 = Task(id="t2", context_id="c1", status=TaskStatus(state=TaskState.WORKING))
        task3 = Task(id="t3", context_id="c2", status=TaskStatus(state=TaskState.SUBMITTED))

        for t in [task1, task2, task3]:
            await agent._store_task(t)

        c1_tasks = await agent._list_tasks("c1")
        assert len(c1_tasks) == 2


class TestRouteHandlers:
    @pytest.mark.asyncio
    async def test_route_get_agent_card(self):
        agent = EchoAgent()
        status, body = await agent._route_agent_card({})
        assert status == 200
        assert "name" in body

    @pytest.mark.asyncio
    async def test_route_get_task_not_found(self):
        agent = EchoAgent()
        from openclawa2a.exceptions import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            await agent._route_get_task("nonexistent", {})

    @pytest.mark.asyncio
    async def test_route_get_task(self):
        agent = EchoAgent()
        task = Task(
            id="t-1",
            context_id="c-1",
            status=TaskStatus(state=TaskState.WORKING),
        )
        await agent._store_task(task)

        status, body = await agent._route_get_task("t-1", {})
        assert status == 200
        assert body["id"] == "t-1"

    @pytest.mark.asyncio
    async def test_route_list_tasks(self):
        agent = EchoAgent()
        task = Task(
            id="t-1",
            context_id="c-1",
            status=TaskStatus(state=TaskState.SUBMITTED),
        )
        await agent._store_task(task)

        status, body = await agent._route_list_tasks({"context_id": "c-1"}, {})
        assert status == 200
        assert len(body["tasks"]) == 1

    @pytest.mark.asyncio
    async def test_route_list_tasks_missing_context_id(self):
        agent = EchoAgent()
        from openclawa2a.exceptions import InvalidRequestError

        with pytest.raises(InvalidRequestError):
            await agent._route_list_tasks({}, {})

    @pytest.mark.asyncio
    async def test_route_cancel_task_not_found(self):
        agent = EchoAgent()
        from openclawa2a.exceptions import TaskNotFoundError

        with pytest.raises(TaskNotFoundError):
            await agent._route_cancel_task("nonexistent", {}, {})

    @pytest.mark.asyncio
    async def test_route_cancel_task(self):
        agent = EchoAgent()
        task = Task(
            id="t-1",
            context_id="c-1",
            status=TaskStatus(state=TaskState.WORKING),
        )
        await agent._store_task(task)

        status, body = await agent._route_cancel_task("t-1", {}, {})
        assert status == 200
        assert body["canceled"] is True

        # Verify task was updated
        updated = await agent._get_task("t-1")
        assert updated is not None
        assert updated.status.state == TaskState.CANCELED

    @pytest.mark.asyncio
    async def test_route_send_message(self):
        agent = EchoAgent()
        body = {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello"}],
            },
        }

        status, response = await agent._route_send_message(body, {})
        assert status == 200
        assert "task" in response
        assert "result" in response
        assert response["result"]["role"] == "agent"
        assert "Echo: Hello" in response["result"]["parts"][0]["text"]


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers(self):
        """Broadcasting without subscribers should not raise."""
        agent = EchoAgent()
        from openclawa2a.models import StreamResponse, StreamEventType

        await agent._broadcast(
            "nonexistent-task",
            StreamResponse(type=StreamEventType.HEARTBEAT, heartbeat=True),
        )  # Should not raise


class TestStreaming:
    @pytest.mark.asyncio
    async def test_stream_task_events(self):
        agent = EchoAgent()
        task = Task(
            id="t-1",
            context_id="c-1",
            status=TaskStatus(state=TaskState.WORKING),
        )
        await agent._store_task(task)

        events = []
        async for event in agent._stream_task_events("t-1"):
            events.append(event)
            break  # Just get the connected event

        assert len(events) == 1
        assert events[0].type.value == "connected"


class TestServerLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        agent = EchoAgent(host="127.0.0.1", port=0)  # port=0 picks random free port
        await agent.start()
        assert agent._server is not None
        await agent.stop()
        assert agent._server is None
