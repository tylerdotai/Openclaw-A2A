#!/usr/bin/env python3
"""
Agent Card Registry Manager

Manages the shared agent registry for OpenClaw A2A communication.
Allows agents to register, discover, heartbeat, and sync the registry.

Usage:
    python3 scripts/registry.py --register --agent dexter
    python3 scripts/registry.py --discover --agent hoss
    python3 scripts/registry.py --list
    python3 scripts/registry.py --heartbeat --agent dexter
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "registry" / "agent-cards.json"
DEFAULT_AGENTS = {
    "dexter": {
        "id": "dexter",
        "name": "Dexter",
        "host": "clawbox",
        "ip": "192.168.0.59",
        "public_ip": "68.118.120.94",
        "a2a_port": 8080,
        "a2a_url": "http://192.168.0.59:8080/a2a",
        "skills": ["python", "sdk", "implementation", "deployment"],
    },
    "hoss": {
        "id": "hoss",
        "name": "Hoss",
        "host": "mac-mini",
        "ip": "192.168.0.104",
        "a2a_port": 8081,
        "a2a_url": "http://192.168.0.104:8081/a2a",
        "skills": ["coordination", "discovery", "architecture", "integration"],
    },
    "brad": {
        "id": "brad",
        "name": "Brad",
        "host": "pi-221",
        "ip": "192.168.0.221",
        "a2a_port": 8082,
        "a2a_url": "http://192.168.0.221:8082/a2a",
        "skills": ["audit", "ci-cd", "infrastructure", "monitoring"],
    },
}


def load_registry() -> dict:
    """Load the agent registry from disk."""
    if not REGISTRY_PATH.exists():
        return {"agents": [], "registry_version": "1.0.0"}
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def save_registry(registry: dict) -> None:
    """Save the agent registry to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def git_push() -> None:
    """Push registry changes to GitHub."""
    try:
        subprocess.run(
            ["git", "add", str(REGISTRY_PATH)],
            check=True,
            cwd=REGISTRY_PATH.parent.parent,
        )
        subprocess.run(
            ["git", "commit", "-m", f"chore: update agent registry - {datetime.now().isoformat()}"],
            check=True,
            cwd=REGISTRY_PATH.parent.parent,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            check=True,
            cwd=REGISTRY_PATH.parent.parent,
        )
        print("✓ Registry pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git push failed: {e}", file=sys.stderr)


def git_pull() -> None:
    """Pull latest registry from GitHub."""
    try:
        subprocess.run(
            ["git", "pull", "origin", "main"],
            check=True,
            cwd=REGISTRY_PATH.parent.parent,
        )
        print("✓ Registry pulled from GitHub")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Git pull failed: {e}", file=sys.stderr)


def register_agent(agent_id: str, push: bool = False) -> None:
    """Register or update an agent's card."""
    if agent_id not in DEFAULT_AGENTS:
        print(f"Unknown agent: {agent_id}. Available: {list(DEFAULT_AGENTS.keys())}")
        sys.exit(1)

    registry = load_registry()

    # Remove existing entry if present
    registry["agents"] = [a for a in registry["agents"] if a["id"] != agent_id]

    # Add/update entry
    card = DEFAULT_AGENTS[agent_id].copy()
    card["status"] = "active"
    card["last_seen"] = datetime.now(timezone.utc).isoformat()
    registry["agents"].append(card)

    save_registry(registry)
    print(f"✓ Registered {agent_id}: {card['a2a_url']}")

    if push:
        git_push()


def discover_agent(agent_id: str) -> dict | None:
    """Discover an agent's card."""
    registry = load_registry()
    for agent in registry.get("agents", []):
        if agent["id"] == agent_id:
            return agent
    return None


def list_agents(push: bool = False) -> None:
    """List all registered agents."""
    registry = load_registry()

    if push:
        git_pull()
        registry = load_registry()

    print(f"\n{'='*60}")
    print(f"  OpenClaw A2A Agent Registry v{registry.get('registry_version', '?')}")
    print(f"{'='*60}\n")

    agents = registry.get("agents", [])
    if not agents:
        print("No agents registered. Run --register first.\n")
        return

    for agent in agents:
        status_icon = "🟢" if agent.get("status") == "active" else "🔴"
        print(f"{status_icon} {agent['name']} ({agent['id']})")
        print(f"   Host:     {agent['host']} ({agent['ip']})")
        print(f"   A2A URL:  {agent['a2a_url']}")
        print(f"   Skills:   {', '.join(agent.get('skills', []))}")
        print(f"   Status:   {agent.get('status', 'unknown')}")
        print(f"   Last:     {agent.get('last_seen', 'never')}")
        print()

    print(f"Total: {len(agents)} agent(s)\n")


def heartbeat(agent_id: str, push: bool = False) -> None:
    """Update agent's last_seen timestamp."""
    registry = load_registry()

    found = False
    for agent in registry.get("agents", []):
        if agent["id"] == agent_id:
            agent["last_seen"] = datetime.now(timezone.utc).isoformat()
            agent["status"] = "active"
            found = True
            print(f"✓ Heartbeat from {agent_id}: {agent['last_seen']}")
            break

    if not found:
        print(f"Agent {agent_id} not found. Register first: --register --agent {agent_id}")
        sys.exit(1)

    save_registry(registry)

    if push:
        git_push()


def main():
    parser = argparse.ArgumentParser(description="OpenClaw A2A Agent Registry Manager")
    parser.add_argument("--register", action="store_true", help="Register an agent")
    parser.add_argument("--discover", action="store_true", help="Discover an agent's card")
    parser.add_argument("--list", action="store_true", help="List all agents")
    parser.add_argument("--heartbeat", action="store_true", help="Send heartbeat for an agent")
    parser.add_argument("--agent", type=str, help="Agent ID (dexter, hoss, brad)")
    parser.add_argument("--push", action="store_true", help="Push changes to GitHub")
    parser.add_argument("--pull", action="store_true", help="Pull changes from GitHub before listing")

    args = parser.parse_args()

    if args.list:
        list_agents(push=args.pull)
    elif args.register:
        if not args.agent:
            print("--agent required for --register")
            sys.exit(1)
        register_agent(args.agent, push=args.push)
    elif args.discover:
        if not args.agent:
            print("--agent required for --discover")
            sys.exit(1)
        card = discover_agent(args.agent)
        if card:
            print(json.dumps(card, indent=2))
        else:
            print(f"Agent {args.agent} not found")
            sys.exit(1)
    elif args.heartbeat:
        if not args.agent:
            print("--agent required for --heartbeat")
            sys.exit(1)
        heartbeat(args.agent, push=args.push)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
