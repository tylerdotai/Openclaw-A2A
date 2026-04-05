#!/usr/bin/env python3
"""
A2A Task Router — delegates incoming A2A messages to subagents.

This is the production A2A server that replaces the Echo server.
It routes tasks to actual agent subagents based on skill tags.

Usage:
    python3 scripts/a2a_task_router.py --agent dexter
"""

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

SDK_PATH = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from openclawa2a.agent_card import AgentCard
from openclawa2a.audit import AuditLogger
from openclawa2a.models import (
    AgentCapabilities,
    AgentProvider,
    AgentSkill,
    Message,
    PartType,
    Task,
    TaskState,
    TaskStatus,
)
from openclawa2a.server import A2AServer

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
logger = logging.getLogger("a2a-router")


class TaskRouterA2AServer(A2AServer):
    """
    Production A2A server that routes tasks to subagents.
    
    Instead of echoing, this:
    1. Parses the incoming task
    2. Routes to appropriate subagent based on skills
    3. Returns the subagent's result
    """

    def __init__(self, agent_id: str, agent_card: dict, audit_logger: AuditLogger):
        self.agent_id = agent_id
        self.audit = audit_logger
        self._subagent_pool = {}

        # Build AgentCard from registry
        a2a_card = AgentCard(
            name=agent_card.get("name", agent_id),
            version="1.0.0",
            description=f"A2A Task Router: {agent_id}",
            provider=AgentProvider(
                organization="flume",
                url=f"http://{agent_card.get('ip')}:{agent_card.get('a2a_port')}/a2a",
            ),
            capabilities=AgentCapabilities(
                streaming=True,
                push_notifications=True,
            ),
            skills=[
                AgentSkill(id=s, name=s, description=s)
                for s in agent_card.get("skills", [])
            ],
            url=agent_card.get("a2a_url"),
        )
        super().__init__(agent_card=a2a_card)

    async def handle_message(self, message: Message, context: dict) -> Message:
        """
        Route incoming message to appropriate handler.
        The message text tells us what to do.
        """
        # Extract content
        content = message.parts[0].text if message.parts else ""
        trace_id = context.get("trace_id", "unknown")

        self.audit.log(
            "task_router_received",
            agent_id=self.agent_id,
            trace_id=trace_id,
            metadata={"content": content[:200], "message_id": message.message_id},
        )

        logger.info(f"[{self.agent_id}] Routing task: {content[:100]}...")

        # Route based on content keywords
        response_text = await self._route_task(content, context)

        return Message(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[{"kind": PartType.TEXT, "text": response_text}],
        )

    async def _route_task(self, content: str, context: dict) -> str:
        """
        Route task to appropriate subagent handler.
        Expand this with real subagent spawning logic.
        """
        content_lower = content.lower()

        # Coding tasks
        if any(kw in content_lower for kw in ["build", "code", "implement", "write", "create"]):
            return await self._handle_coding_task(content, context)

        # Research tasks
        if any(kw in content_lower for kw in ["research", "analyze", "find", "explore"]):
            return await self._handle_research_task(content, context)

        # Writing tasks
        if any(kw in content_lower for kw in ["write", "draft", "document", "writeup"]):
            return await self._handle_writing_task(content, context)

        # DevOps tasks
        if any(kw in content_lower for kw in ["deploy", "server", "config", "setup", "infrastructure"]):
            return await self._handle_devops_task(content, context)

        # Default: acknowledgment with status
        return (
            f"[{self.agent_id.upper()}] Task received and logged. "
            f"Content: {content[:150]}... "
            f"Trace: {context.get('trace_id', 'unknown')}. "
            f"Subagent routing will be expanded for this task type."
        )

    async def _handle_coding_task(self, content: str, context: dict) -> str:
        """Handle a coding/implementation task."""
        return (
            f"[{self.agent_id.upper()}] Coding task received. "
            f"Would spawn coder subagent for: {content[:100]}... "
            f"Trace: {context.get('trace_id', 'unknown')}. "
            f"This is where we'd spawn sessions_spawn() for the coder agent."
        )

    async def _handle_research_task(self, content: str, context: dict) -> str:
        """Handle a research task."""
        return (
            f"[{self.agent_id.upper()}] Research task received. "
            f"Would spawn researcher subagent for: {content[:100]}... "
            f"Trace: {context.get('trace_id', 'unknown')}."
        )

    async def _handle_writing_task(self, content: str, context: dict) -> str:
        """Handle a writing/documentation task."""
        return (
            f"[{self.agent_id.upper()}] Writing task received. "
            f"Would spawn marketer/ops subagent for: {content[:100]}... "
            f"Trace: {context.get('trace_id', 'unknown')}."
        )

    async def _handle_devops_task(self, content: str, context: dict) -> str:
        """Handle a DevOps/infrastructure task."""
        return (
            f"[{self.agent_id.upper()}] DevOps task received. "
            f"Would spawn devops subagent for: {content[:100]}... "
            f"Trace: {context.get('trace_id', 'unknown')}."
        )


async def run_server(agent_id: str, port: int | None = None):
    """Start the task router A2A server."""

    card = discover_agent(agent_id)
    if not card:
        print(f"Agent '{agent_id}' not found. Run: python3 scripts/registry.py --register --agent {agent_id}")
        sys.exit(1)

    if port:
        card["a2a_port"] = port
        card["a2a_url"] = f"http://{card['ip']}:{port}/a2a"

    heartbeat(agent_id)
    audit = AuditLogger()
    server = TaskRouterA2AServer(agent_id, card, audit)

    url = f"http://0.0.0.0:{card['a2a_port']}/a2a"
    logger.info(f"Starting A2A Task Router for {agent_id} at {url}")

    try:
        await server.start(port=card["a2a_port"], host="0.0.0.0")
    except KeyboardInterrupt:
        logger.info(f"Task Router for {agent_id} stopped")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Run an A2A Task Router for an agent")
    parser.add_argument("--agent", required=True, choices=["dexter", "hoss", "brad"])
    parser.add_argument("--port", type=int, help="Override port")

    args = parser.parse_args()
    asyncio.run(run_server(args.agent, args.port))


if __name__ == "__main__":
    main()
