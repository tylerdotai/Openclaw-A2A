# OpenClaw-A2A

**Hardened A2A Protocol Implementation for OpenClaw Agents**

[![PyPI Version](https://img.shields.io/pypi/v/openclawa2a?color=%23ff6b00)](https://pypi.org/project/openclawa2a)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![A2A Spec](https://img.shields.io/badge/A2A%20Protocol-v1.0-%23ff6b00)](https://github.com/a2aproject/A2A)

---

## Overview

OpenClaw-A2A is a production-hardened implementation of the [Agent-to-Agent (A2A) Protocol v1](https://github.com/a2aproject/A2A) built specifically for the [OpenClaw](https://github.com/openclaw) agent runtime. It extends the base A2A specification with structured audit logging, cross-agent coordination skills, streaming fidelity, and operational tooling required for production multi-agent systems.

The A2A protocol enables agents to communicate, delegate tasks, and coordinate as a mesh — rather than as isolated instances. OpenClaw-A2A brings that capability into the OpenClaw ecosystem with the reliability guarantees that production deployments demand.

**This is a community fork** of the upstream [A2A](https://github.com/a2aproject/A2A) project, maintained by the [OpenClaw team](https://github.com/tylerdotai/Openclaw-A2A). It tracks the upstream specification while layering on OpenClaw-specific integrations.

---

## Why A2A?

Modern AI agent systems rarely operate in isolation. As agentic workflows grow more sophisticated, agents need to:

- **Delegate work** to specialized sub-agents and receive results
- **Discover each other's capabilities** at runtime without hardcoded endpoints
- **Maintain conversation context** across long-running, multi-turn tasks
- **Stream incremental updates** back to callers rather than blocking until completion

A2A addresses all of these. It is purpose-built for agent-to-agent communication, whereas MCP (Model Context Protocol) is optimized for agent-to-tool interactions. The two protocols are complementary — MCP connects an agent to external tools and data; A2A connects agents to each other.

### A2A vs MCP

| Concern | A2A | MCP |
|---------|-----|-----|
| Primary use case | Agent ↔ Agent communication | Agent ↔ Tool/resource access |
| Discovery | Agent Cards (runtime) | Static tool manifests |
| Conversations | Yes — multi-turn, stateful | No — stateless request/response |
| Streaming | Task Arts (progressive updates) | Not natively |
| Best for | Delegation, orchestration, mesh | Tool calls, RAG, database access |

In practice, a production OpenClaw agent stack uses both: MCP for tools and data, A2A for inter-agent coordination.

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenClaw Agent                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  A2A Client  │───▶│  A2A Server  │◀───│  Agent Card       │  │
│  │  (outbound)  │    │  (inbound)   │    │  (capabilities)   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────────────────┘  │
│         │                   │                                    │
│         ▼                   ▼                                    │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │ Audit Logger │    │  Tracing     │                           │
│  └──────────────┘    └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
              │                   │
              ▼                   ▼
       ┌────────────┐      ┌────────────┐
       │  Remote    │      │  Remote    │
       │  A2A Agent │      │  A2A Agent │
       └────────────┘      └────────────┘
         (A2A Client)        (A2A Server)
```

### Components

| Component | Description | Location |
|-----------|-------------|----------|
| `openclawa2a.client` | A2A client for sending tasks and streaming responses | `sdk/python/openclawa2a/client.py` |
| `openclawa2a.server` | A2A server for receiving and handling inbound tasks | `sdk/python/openclawa2a/server.py` |
| `openclawa2a.models` | Pydantic models for all A2A protocol types | `sdk/python/openclawa2a/models.py` |
| `openclawa2a.agent_card` | Agent Card generation and parsing | `sdk/python/openclawa2a/agent_card.py` |
| `openclawa2a.tracing` | Distributed tracing for cross-agent spans | `sdk/python/openclawa2a/tracing.py` |
| `openclawa2a.audit` | Structured audit logger for all A2A events | `sdk/python/openclawa2a/audit.py` |
| `openclawa2a.exceptions` | Typed exception hierarchy | `sdk/python/openclawa2a/exceptions.py` |
| `audit/` | Standalone audit module with query CLI | `audit/` |
| `skills/a2a-audit/` | OpenClaw skill for audit log queries | `skills/a2a-audit/` |
| `skills/openclaw-a2a-coordination/` | OpenClaw skill for orchestration patterns | `skills/openclaw-a2a-coordination/` |

### Agent Card

Every A2A agent publishes an **Agent Card** — a JSON document describing its capabilities, supported skills, authentication requirements, and endpoint. This enables runtime discovery without static configuration.

```json
{
  "name": "dexter",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "skills": [
    { "id": "repo-scanner", "name": "Repository Scanner" },
    { "id": "a2a-audit",    "name": "Audit Log Query" }
  ],
  "endpoint": "http://localhost:18789/a2a"
}
```

---

## Quick Start

Get a two-agent OpenClaw system communicating over A2A in five steps.

### 1. Install the SDK

```bash
pip install openclawa2a
```

### 2. Define an Agent Card

```python
from openclawa2a import AgentCard

card = AgentCard(
    name="my-agent",
    version="1.0.0",
    endpoint="http://localhost:18789/a2a",
    capabilities={"streaming": True}
)
```

### 3. Start an A2A Server

```python
from openclawa2a import A2AServer
from openclawa2a.models import Task, TaskStatus

server = A2AServer(agent_card=card)

@server.on_task
async def handle_task(task: Task) -> Task:
    # Process the task — delegate, orchestrate, compute
    task.status = TaskStatus.COMPLETED
    task.output = {"result": "done"}
    return task

server.start(host="0.0.0.0", port=18789)
```

### 4. Discover and Send a Task

```python
from openclawa2a import A2AClient

# Discover agent via Agent Card
client = A2AClient()

# Fetch remote agent card
agent_card = await client.discover("http://remote-agent:18789/.well-known/agent.json")

# Send a task
task = await client.send_task(
    agent_card=agent_card,
    task={
        "id": "task-001",
        "input": {"prompt": "Analyze the Flume wiki for undocumented endpoints."}
    }
)
print(task.output)
```

### 5. Enable Audit Logging

```python
from openclawa2a.audit import A2AAuditLogger

audit = A2AAuditLogger(log_dir="audit/logs")

audit.task_created(
    source="hoss",
    target="dexter",
    task_id="task-001",
    content="Analyze the Flume wiki"
)

# ... after task completes ...

audit.task_updated(
    source="dexter",
    target="hoss",
    task_id="task-001",
    status="completed",
    metadata={"duration_ms": 12450}
)
```

Query the logs:

```bash
python3 audit/query.py --agent dexster --date 2026-04-05
```

---

## Installation

### pip

```bash
pip install openclawa2a
```

For optional streaming and async extras:

```bash
pip install "openclawa2a[streaming,async]"
```

### Docker

```bash
docker pull ghcr.io/tylerdotai/openclaw-a2a:latest
docker run -p 18789:18789 ghcr.io/tylerdotai/openclaw-a2a:latest
```

### Build from Source

```bash
git clone https://github.com/tylerdotai/Openclaw-A2A.git
cd Openclaw-A2A
pip install -e sdk/python/
```

Or use the build script:

```bash
bash scripts/build.sh all
```

---

## Usage Examples

### Sending a Task with Streaming

```python
from openclawa2a import A2AClient
from openclawa2a.models import TaskUpdate

client = A2AClient()

async for update in client.send_task_streaming(agent_card, task):
    if isinstance(update, TaskUpdate):
        print(f"Status: {update.status}")
        if update.artifacts:
            print(f"Partial result: {update.artifacts[-1]}")
```

### Agent Discovery

```python
from openclawa2a import A2AClient

client = A2AClient()

# Discover by well-known URL
card = await client.discover("http://target-agent:18789/.well-known/agent.json")

# Or discover from a directory
cards = await client.discover_directory("http://registry.internal/v1/agents")
```

### A2A Server with Skill Routing

```python
from openclawa2a import A2AServer, AgentCard
from openclawa2a.models import Task

server = A2AServer(AgentCard(name="orchestrator", version="1.0.0", endpoint="..."))

@server.on_task(skill="repo-scanner")
async def scan(task: Task) -> Task:
    # Route to the repo-scanner skill handler
    result = await run_repo_scanner(task.input)
    task.output = result
    return task

@server.on_task(skill="a2a-audit")
async def audit_query(task: Task) -> Task:
    # Route to the audit skill handler
    result = await query_audit_logs(task.input)
    task.output = result
    return task

server.start()
```

### Multi-Agent Coordination Pattern

```python
from openclawa2a import A2AClient
from openclawa2a.audit import A2AAuditLogger

audit = A2AAuditLogger()
client = A2AClient()

async def orchestrate(goal: str, agent_cards: list[AgentCard]) -> dict:
    plan = await client.send_task(
        agent_card=agent_cards[0],  # Planner agent
        task={"input": {"goal": goal, "agents": agent_cards}}
    )
    subtasks = plan.output["subtasks"]

    results = []
    for subtask in subtasks:
        audit.task_created(
            source="orchestrator",
            target=subtask["agent"],
            task_id=subtask["id"],
            content=subtask["description"]
        )
        result = await client.send_task(
            agent_card=find_card(agent_cards, subtask["agent"]),
            task=subtask
        )
        results.append(result)
        audit.task_updated(
            source=subtask["agent"],
            target="orchestrator",
            task_id=subtask["id"],
            status="completed"
        )

    return {"results": results}
```

---

## API Reference

The OpenClaw-A2A SDK implements the full [A2A Protocol v1 Specification](https://github.com/a2aproject/A2A/tree/trunk/specification).

Full API documentation: [`docs/specification.md`](docs/specification.md)

Key types:

| Type | Description |
|------|-------------|
| `AgentCard` | Capability manifest published by an A2A agent |
| `Task` | Work item passed between agents |
| `TaskUpdate` | Streaming status/artifact update |
| `Message` | Single turn message within a Task |
| `TaskStatus` | Enum: `pending`, `working`, `completed`, `failed`, `cancelled` |
| `Artifact` | Output artifact produced by a task |
| `PushNotification` | Server-initiated push to client |

---

## SDK Reference

Python SDK: [`docs/sdk/python.md`](docs/sdk/python.md)

The Python SDK is organized under `sdk/python/openclawa2a/`:

```
sdk/python/openclawa2a/
├── __init__.py       # Public exports
├── client.py         # A2AClient
├── server.py         # A2AServer
├── models.py         # Pydantic models
├── agent_card.py     # Card types and parsing
├── tracing.py        # Distributed tracing
├── audit.py          # AuditLogger (SDK-level)
├── exceptions.py     # Typed error hierarchy
└── py.typed          # PEP 561 marker
```

---

## Skills

OpenClaw-A2A ships with two OpenClaw skills that integrate directly with the OpenClaw agent runtime.

### `skills/a2a-audit` — Audit Log Query Skill

Query A2A audit logs from within an OpenClaw agent conversation.

```
/a2a-audit --agent hoss --date 2026-04-05 --limit 20
/a2a-audit --task-id <uuid>
/a2a-audit --event-type error --since 2026-04-01
```

See [`skills/a2a-audit/SKILL.md`](skills/a2a-audit/SKILL.md) for full documentation.

### `skills/openclaw-a2a-coordination` — Coordination Skill

High-level orchestration patterns: fan-out, fan-in, pipeline, and monitor patterns for multi-agent coordination.

See [`skills/openclaw-a2a-coordination/SKILL.md`](skills/openclaw-a2a-coordination/SKILL.md) for full documentation.

---

## Contributing

Contributions are welcome. This is a community fork — all PRs go to [`github.com/tylerdotai/Openclaw-A2A`](https://github.com/tylerdotai/Openclaw-A2A).

### Workflow

1. **Fork** the repository: `https://github.com/tylerdotai/Openclaw-A2A`
2. **Clone** your fork:
   ```bash
   git clone https://github.com/your-username/Openclaw-A2A.git
   cd Openclaw-A2A
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feat/your-feature-name
   ```
4. **Install dev dependencies:**
   ```bash
   pip install -e "sdk/python/[dev]"
   pre-commit install
   ```
5. **Make your changes.** Keep commits atomic and write tests.
6. **Run the build pipeline:**
   ```bash
   bash scripts/build.sh all
   ```
7. **Push and open a PR** against `main` on `tylerdotai/Openclaw-A2A`.

### Reporting Issues

Report bugs and feature requests via [GitHub Issues](https://github.com/tylerdotai/Openclaw-A2A/issues). For security issues, see the Security section below.

### Code Style

- Python: PEP 8, enforced via `ruff`
- Types: Pydantic v2 for all protocol models
- Tests: `pytest` with ≥80% coverage requirement
- Docs: Markdown, built with MkDocs

---

## Security

### Authentication

A2A endpoints should be protected by authentication in production. OpenClaw-A2A supports:

- **Token authentication** via `Authorization: Bearer <token>` header
- **MTLS** for network-level encryption in mesh deployments
- **Agent Card signed metadata** for verified agent identity

Pass credentials at client construction:

```python
client = A2AClient(auth_token="your-token")
server = A2AServer(auth_token="your-token")
```

### Responsible Disclosure

Security vulnerabilities in OpenClaw-A2A should be reported privately. Do not file public GitHub issues for security problems.

**Please report via:**

1. Email the maintainers directly through their GitHub profiles
2. Or file a private security advisory on GitHub

We aim to acknowledge within 48 hours and resolve within 90 days. We follow a standard CVSS-based severity rating.

---

## Audit & Trace

### How Audit Logging Works

Every A2A event in OpenClaw-A2A is written to a structured JSONL audit log. The log is:

- **Daily rolling** — one file per day in `audit/logs/a2a-audit-YYYY-MM-DD.jsonl`
- **Structured** — every entry includes timestamp, source, target, event type, status, and metadata
- **Queryable** — use `audit/query.py` to search by agent, task ID, date range, or event type
- **Non-blocking** — audit writes are synchronous but IO-optimized; they do not block task execution

### Log Schema

```json
{
  "timestamp": "2026-04-05T12:34:56.789Z",
  "version": "1.0.0",
  "event_type": "task_created",
  "source_agent": "hoss",
  "target_agent": "dexter",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "660e8400-e29b-41d4-a716-446655440001",
  "content_summary": "Analyze the Flume wiki for undocumented endpoints.",
  "status": "pending",
  "metadata": {}
}
```

### Event Types

| Event | Meaning |
|-------|---------|
| `task_created` | A new task was initiated by an agent |
| `task_updated` | A task transitioned to a new status |
| `message_sent` | An A2A message was dispatched |
| `message_received` | An A2A message was received and processed |
| `agent_discovered` | An Agent Card was fetched and parsed |
| `skill_invoked` | A cross-agent skill call was executed |
| `error` | A communication or protocol error occurred |

### Retention

| Log Tier | Retention | Storage |
|----------|-----------|---------|
| Daily JSONL | 30 days | `audit/logs/` |
| Weekly summary | 90 days | `audit/summaries/` |
| Critical errors | 1 year | `audit/critical/` |

---

## Roadmap

The OpenClaw-A2A roadmap tracks both upstream A2A spec developments and OpenClaw-specific enhancements.

### In Progress
- [ ] OpenClaw skill for A2A agent registration/discovery
- [ ] Streaming support with SSE backpressure handling
- [ ] GitHub Actions CI pipeline (see [`BUILD_RULES.md`](BUILD_RULES.md))

### Planned
- [ ] Typed TypeScript/JS SDK alongside the Python SDK
- [ ] Agent registry integration (OpenClaw agent directory)
- [ ] Push notification support (A2A `pushNotifications` capability)
- [ ] OpenTelemetry trace propagation across agent boundaries
- [ ] Distributed task queue adapter (Celery/Redis backend option)
- [ ] Production deployment manifests (Docker Compose, Kubernetes Helm)

### Upstream Tracking
We track [upstream A2A spec](https://github.com/a2aproject/A2A) developments. OpenClaw-A2A will adopt ratified spec changes promptly.

---

## License

OpenClaw-A2A is licensed under the [Apache 2.0 License](LICENSE). It is a community fork of the [A2A Protocol](https://github.com/a2aproject/A2A) project.

---

## Links

- **Upstream A2A:** https://github.com/a2aproject/A2A
- **OpenClaw-A2A Fork:** https://github.com/tylerdotai/Openclaw-A2A
- **Specification:** [`docs/specification.md`](docs/specification.md)
- **Python SDK Docs:** [`docs/sdk/python.md`](docs/sdk/python.md)
- **OpenClaw:** https://github.com/openclaw

---
