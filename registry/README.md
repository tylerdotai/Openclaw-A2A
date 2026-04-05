# Agent Card Registry

Shared registry of all OpenClaw A2A agents. Each agent's card is stored here for discovery.

## Quick Start

```bash
# Register your agent (updates last_seen)
python3 scripts/registry.py --register --agent dexter

# List all agents
python3 scripts/registry.py --list

# Get a specific agent's card
python3 scripts/registry.py --discover --agent hoss

# Heartbeat (update your presence)
python3 scripts/registry.py --heartbeat --agent dexter

# Pull latest from GitHub before listing
python3 scripts/registry.py --list --pull
```

## Agent Cards

Each agent card contains:

```json
{
  "id": "dexter",
  "name": "Dexter",
  "host": "clawbox",
  "ip": "192.168.0.59",
  "public_ip": "68.118.120.94",
  "a2a_port": 8080,
  "a2a_url": "http://192.168.0.59:8080/a2a",
  "skills": ["python", "sdk", "implementation", "deployment"],
  "status": "active",
  "last_seen": "2026-04-05T16:15:00Z"
}
```

## Current Agents

| Agent | Host | IP | Port | Skills |
|-------|------|-----|------|--------|
| Dexter | clawbox (Ubuntu) | 192.168.0.59 | 8080 | python, sdk, implementation, deployment |
| Hoss | Mac mini M4 | 192.168.0.104 | 8081 | coordination, discovery, architecture, integration |
| Brad | Pi 4 | 192.168.0.221 | 8082 | audit, ci-cd, infrastructure, monitoring |

## How Discovery Works

1. Agent A wants to send to Agent B
2. Agent A reads `registry/agent-cards.json` (or pulls from GitHub)
3. Agent A finds B's `a2a_url`
4. Agent A uses SDK: `A2AClient(b_url).send_message(...)`
5. Agent B's A2A server receives and processes

## Sync Strategy

- Each agent updates its own card on startup with `--register`
- Cards are pushed to GitHub
- Other agents pull before sending messages
- Low-frequency sync (startup + hourly heartbeat is sufficient)

## Files

```
registry/
├── agent-cards.json    # The shared registry
└── README.md           # This file
```
