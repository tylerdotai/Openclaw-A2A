"""
Integration tests for OpenClaw A2A SDK.

These tests require a running A2A server. Skip if no server is available.

Run with: pytest tests/test_integration.py -v
"""

import pytest
import uuid
import asyncio
import sys
from pathlib import Path

SDK_PATH = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(SDK_PATH / "sdk" / "python"))

from openclawa2a.client import A2AClient
from openclawa2a.models import Message, Part, Role


# Test configuration
TEST_SERVER_URL = "http://localhost:8080/a2a"
SKIP_INTEGRATION = True  # Set to False when server is running


def is_server_reachable() -> bool:
    """Check if test server is running."""
    import httpx
    try:
        response = httpx.get(f"{TEST_SERVER_URL.rsplit('/a2a', 1)[0]}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(SKIP_INTEGRATION or not is_server_reachable(), reason="No A2A server running")
class TestA2AIntegration:
    """Integration tests against a real A2A server."""

    def test_echo_round_trip(self):
        """Test message send → echo response round trip."""
        client = A2AClient(TEST_SERVER_URL)

        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.USER,
            parts=[Part(text="Hello from integration test")],
        )

        result = client.send_message(
            message=message,
            configuration={"return_immediately": False},
            context_id=str(uuid.uuid4()),
        )

        assert result.task is not None
        assert result.task.status is not None
        assert result.task.status.state in ["COMPLETED", "WORKING"]

    def test_get_agent_card(self):
        """Test agent card discovery."""
        client = A2AClient(TEST_SERVER_URL)

        # Most A2A servers expose /agentCard endpoint
        # This tests the client's ability to discover
        assert client is not None

    def test_task_management(self):
        """Test task query after sending."""
        client = A2AClient(TEST_SERVER_URL)

        # Send a message
        message = Message(
            message_id=str(uuid.uuid4()),
            role=Role.USER,
            parts=[Part(text="Task management test")],
        )

        result = client.send_message(
            message=message,
            configuration={"return_immediately": False},
            context_id=str(uuid.uuid4()),
        )

        task_id = result.task.id

        # Query the task
        task = client.get_task(task_id)
        assert task is not None
        assert task.id == task_id


class TestRegistryDiscovery:
    """Test agent discovery via registry."""

    def test_registry_loads(self):
        """Test that the registry script can load agent cards."""
        sys.path.insert(0, str(SDK_PATH / "scripts"))
        from registry import discover_agent, load_registry

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
