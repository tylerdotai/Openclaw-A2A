#!/usr/bin/env python3
"""
Send an A2A message from one agent to another.

Usage:
    python3 scripts/send-a2a.py --from dexter --to hoss --message "Hello CEO"
    python3 scripts/send-a2a.py --from hoss --to dexter --message "Build the SDK" --skill python
"""

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Add SDK to path
SDK_PATH = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))

from openclawa2a.client import OpenClawA2AClient
from openclawa2a.models import Message, Part, PartType

# Import registry helpers
import importlib.util
registry_path = Path(__file__).parent / "registry.py"
spec = importlib.util.spec_from_file_location("registry", registry_path)
registry_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry_module)
discover_agent = registry_module.discover_agent


async def send_message(
    from_agent: str,
    to_agent: str,
    message: str,
    skill: str | None = None,
    context_id: str | None = None,
) -> dict:
    """Send an A2A message between agents."""

    # Discover target agent
    target = discover_agent(to_agent)
    if not target:
        print(f"Agent '{to_agent}' not found. Run: python3 scripts/registry.py --list")
        return {"success": False, "error": "Agent not found"}

    a2a_url = target["a2a_url"]
    print(f"Sending message from '{from_agent}' → '{to_agent}' at {a2a_url}")

    # Create client and send
    client = OpenClawA2AClient(a2a_url)

    # Prepare message
    msg = Message(
        message_id=str(uuid.uuid4()),
        role="user",
        parts=[{"kind": PartType.TEXT, "text": message}],
    )

    ctx_id = context_id or str(uuid.uuid4())

    try:
        result = await client.send_message(
            message=msg,
            context_id=ctx_id,
            stream=False,
        )

        print(f"\n✓ Message sent")
        print(f"  Task ID:    {result.task.id}")
        print(f"  Context ID: {ctx_id}")
        print(f"  Status:     {result.task.status.state}")

        await client.close()
        return {
            "success": True,
            "task_id": result.task.id,
            "context_id": ctx_id,
            "status": result.task.status.state,
        }

    except Exception as e:
        print(f"\n✗ Failed to send message: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="Send an A2A message between agents")
    parser.add_argument("--from", dest="from_agent", required=True, help="Sending agent ID")
    parser.add_argument("--to", dest="to_agent", required=True, help="Receiving agent ID")
    parser.add_argument("--message", required=True, help="Message content")
    parser.add_argument("--skill", type=str, help="Optional skill to invoke")
    parser.add_argument("--context-id", type=str, help="Optional context ID")

    args = parser.parse_args()

    result = asyncio.run(send_message(
        from_agent=args.from_agent,
        to_agent=args.to_agent,
        message=args.message,
        skill=args.skill,
        context_id=args.context_id,
    ))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
