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

from openclawa2a.agent_card import AgentCardBuilder
from openclawa2a.audit import AuditLogger
from openclawa2a.models import Message, Task, TaskState, TaskStatus
from openclawa2a.server import A2AServer
from scripts.registry import discover_agent, heartbeat

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
        super().__init__(agent_card=AgentCardBuilder.from_dict(agent_card).build())

    async def on_message(self, message: Message) -> Task:
        """Handle incoming message — echo back with a response."""
        # Log receipt
        self.audit.message_received(
            source="remote",
            target=self.agent_id,
            message_id=message.message_id,
            content=message.parts[0].text if message.parts else "",
        )

        # Create echo response task
        echo_text = f"[{self.agent_id.upper()}] Echo: {message.parts[0].text if message.parts else '(empty)'}"

        task = Task(
            id=str(uuid.uuid4()),
            context_id=message.context_id,
            status=TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(
                    message_id=str(uuid.uuid4()),
                    role="agent",
                    parts=[{"text": echo_text}],
                ),
            ),
            artifacts=[{
                "artifact_id": str(uuid.uuid4()),
                "name": "echo-response",
                "parts": [{"text": echo_text}],
            }],
        )

        # Log task completion
        self.audit.task_updated(
            source=self.agent_id,
            target="remote",
            task_id=task.id,
            status="completed",
        )

        logger.info(f"Processed message {message.message_id} → task {task.id}")
        return task


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
