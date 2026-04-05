"""
Integration tests for OpenClaw A2A SDK.

These tests require running A2A servers. They are automatically skipped if no server is available.

Run with: pytest tests/test_integration.py -v
"""

import pytest
import uuid
import sys
from pathlib import Path

SDK_PATH = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(SDK_PATH / "sdk" / "python"))

from openclawa2a.client import OpenClawA2AClient
from openclawa2a.models import Message, Part, PartType, Role, TaskState


# Test configuration — use Dexter's local server
TEST_SERVER_URL = "http://localhost:8080"
SKIP_INTEGRATION = False  # Set to True to skip even when server is reachable


def is_server_reachable() -> bool:
    """Check if test server is running."""
    import httpx
    try:
        response = httpx.get(f"{TEST_SERVER_URL}/agent-card", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


# Only run integration tests if a server is reachable
run_integration = not SKIP_INTEGRATION and is_server_reachable()


@pytest.mark.skipif(not run_integration, reason="No A2A server running")
class TestA2AIntegration:
    """Integration tests against a real A2A server."""

    @pytest.mark.asyncio
    async def test_echo_round_trip(self):
        """Test message send → echo response round trip."""
        client = OpenClawA2AClient(TEST_SERVER_URL)

        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.USER,
            parts=[Part(kind=PartType.TEXT, text="Hello from integration test")],
        )

        result = await client.send_message(message=message, stream=False)

        assert result.task is not None
        assert result.task.status is not None
        assert result.task.status.state in {
            TaskState.COMPLETED,
            TaskState.WORKING,
            TaskState.SUBMITTED,
        }

    @pytest.mark.asyncio
    async def test_get_agent_card(self):
        """Test agent card discovery."""
        client = OpenClawA2AClient(TEST_SERVER_URL)

        card = await client.get_agent_card()
        assert card is not None
        assert card.name in ("Dexter", "Hoss", "Brad")
        assert card.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_task_management(self):
        """Test task query after sending."""
        client = OpenClawA2AClient(TEST_SERVER_URL)

        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.USER,
            parts=[Part(kind=PartType.TEXT, text="Task management test")],
        )

        result = await client.send_message(message=message, stream=False)
        task_id = result.task.id

        # Query the task
        task = await client.get_task(task_id)
        assert task is not None
        assert task.id == task_id


@pytest.mark.skipif(not run_integration, reason="No A2A server running")
class TestRegistryDiscovery:
    """Test agent discovery via registry."""

    def test_registry_loads(self):
        """Test that the registry script can load agent cards."""
        sys.path.insert(0, str(SDK_PATH / "scripts"))
        from registry import load_registry

        registry = load_registry()
        assert "agents" in registry
        assert len(registry["agents"]) >= 3

    def test_dexter_in_registry(self):
        """Test that Dexter's card is in the registry."""
        sys.path.insert(0, str(SDK_PATH / "scripts"))
        from registry import discover_agent

        card = discover_agent("dexter")
        assert card is not None
        assert card["id"] == "dexter"
        assert "a2a_url" in card

    def test_all_agents_in_registry(self):
        """Test that all three agents are registered."""
        sys.path.insert(0, str(SDK_PATH / "scripts"))
        from registry import load_registry

        registry = load_registry()
        agent_ids = {a["id"] for a in registry["agents"]}

        assert "dexter" in agent_ids
        assert "hoss" in agent_ids
        assert "brad" in agent_ids
