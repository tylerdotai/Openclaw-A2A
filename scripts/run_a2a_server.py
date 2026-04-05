#!/usr/bin/env python3
"""
Run an A2A Server for a specific agent.

Starts an A2A server on the agent's registered port, using the
Agent Card from the registry.

Usage:
    python3 scripts/run-a2a-server.py --agent dexter
    python3 scripts/run-a2a-server.py --agent hoss --port 8081
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
import uuid
from pathlib import Path

# Add SDK to path
SDK_PATH = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from openclawa2a.agent_card import AgentCard
from openclawa2a.audit import AuditLogger
from openclawa2a.models import AgentCapabilities, AgentProvider, AgentSkill, Message, PartType
from openclawa2a.server import A2AServer

# Import registry helpers
import importlib.util
registry_path = Path(__file__).parent / "registry.py"
spec = importlib.util.spec_from_file_location("registry", registry_path)
registry_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry_module)
discover_agent = registry_module.discover_agent
heartbeat = registry_module.heartbeat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("a2a-server")


class EchoA2AServer(A2AServer):
    """Simple echo server for testing A2A communication."""

    def __init__(self, agent_id: str, agent_card: dict, audit_logger: AuditLogger):
        self.agent_id = agent_id
        self.audit = audit_logger

        # Build proper AgentCard from registry card (simplified format)
        a2a_card = AgentCard(
            name=agent_card.get("name", agent_id),
            version="1.0.0",
            description=f"A2A agent: {agent_id}",
            provider=AgentProvider(
                organization="flume",
                url=f"http://{agent_card.get('ip')}:{agent_card.get('a2a_port')}/a2a",
            ),
            capabilities=AgentCapabilities(
                streaming=True,
                push_notifications=True,
            ),
            skills=[AgentSkill(id=s, name=s, description=s) for s in agent_card.get("skills", [])],
            url=agent_card.get("a2a_url"),
        )
        super().__init__(agent_card=a2a_card)

    async def handle_message(self, message: Message, context: dict) -> Message:
        """Handle incoming message — echo back with a response."""
        content = message.parts[0].text if message.parts else "(empty)"

        # Log receipt
        self.audit.log(
            "message_received",
            agent_id=self.agent_id,
            metadata={"message_id": message.message_id, "content": content},
        )

        # Create echo response
        echo_text = f"[{self.agent_id.upper()}] Echo: {content}"

        logger.info(f"Processed message {message.message_id}")
        return Message(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[{"kind": PartType.TEXT, "text": echo_text}],
        )


async def run_server(agent_id: str, port: int | None = None):
    """Start the A2A server."""

    # Discover agent card
    card = discover_agent(agent_id)
    if not card:
        print(f"Agent '{agent_id}' not found. Run: python3 scripts/registry.py --register --agent {agent_id}")
        sys.exit(1)

    # Override port if specified
    if port:
        card["a2a_port"] = port
        card["a2a_url"] = f"http://{card['ip']}:{port}/a2a"

    # Update heartbeat
    heartbeat(agent_id)

    # Create audit logger
    audit = AuditLogger()

    # Create server
    server = EchoA2AServer(agent_id, card, audit)

    # Start server
    url = f"http://0.0.0.0:{card['a2a_port']}/a2a"
    logger.info(f"Starting A2A server for {agent_id} at {url}")

    try:
        await server.start(port=card["a2a_port"], host="0.0.0.0")
    except KeyboardInterrupt:
        logger.info(f"Server for {agent_id} stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Run an A2A server for an agent")
    parser.add_argument("--agent", required=True, choices=["dexter", "hoss", "brad"], help="Agent ID")
    parser.add_argument("--port", type=int, help="Override port (default: from registry)")

    args = parser.parse_args()

    asyncio.run(run_server(args.agent, args.port))


if __name__ == "__main__":
    main()
