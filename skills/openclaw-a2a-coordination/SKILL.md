# OpenClaw-A2A Coordination Skill

Skill for OpenClaw agents working on the OpenClaw-A2A project.

## Project Overview
OpenClaw-A2A is Tyler's fork of the A2A (Agent2Agent) protocol, hardened for production use by the Hydra Mesh agent team.

**Repo:** https://github.com/tylerdotai/OpenClaw-A2A  
**Upstream:** https://github.com/a2aproject/A2A

## Team Roles

| Agent | Role | Domain |
|-------|------|--------|
| Hoss | Architecture & Spec | A2A spec deep-dive, integration pattern design |
| Dexter | SDK Implementation | Python SDK, agent card generation, task protocol |
| Brad | Infrastructure & Skills | CI/CD, build scripts, skill templates, audit |

## Core Workflow

### Before Starting Work
1. Check `#personal-intelligence` Discord for coordination messages
2. Review `AGENTS.md` in repo root for current task assignments
3. Check wiki at https://github.com/tylerdotai/flume-wiki for context
4. Update `memory/YYYY-MM-DD.md` with what you're working on

### Delegation Rules
- **Sub-agents:** Use `sessions_spawn` with specific tasks, not vague instructions
- **Timeouts:** 120-180s for research, 300-600s for implementation, 900s+ for full builds
- **Parallelize:** If two tasks are independent, spawn them simultaneously
- **Don't overlap:** Check AGENTS.md before starting — if someone else owns it, defer

### Communication
- **Primary:** Discord `#personal-intelligence`
- **Mesh relay:** Titan :8500 (currently down — use Discord fallback)
- **Documentation:** Wiki + repo README

## A2A Protocol Reference

### Key Concepts
- **Agent Card:** JSON metadata document for agent discovery
- **Task:** Stateful unit of work with unique ID and lifecycle
- **Message:** Single turn of communication (user or agent role)
- **Part:** Content container (text, raw bytes, URL, or structured data)
- **Artifact:** Tangible output (document, image, code)

### Protocol Stack
```
HTTP/S → JSON-RPC 2.0 → A2A Service
                          ├── SendMessage (request/response)
                          ├── SendStreamingMessage (SSE)
                          ├── GetTask / ListTasks
                          ├── CancelTask
                          └── SubscribeToTask (SSE)
```

### Agent Card Schema (Key Fields)
```json
{
  "name": "string",
  "description": "string",
  "url": "https://endpoint/...",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    { "id": "skill-id", "name": "string", "description": "string" }
  ],
  "authentication": { "type": "none" | "bearer" | "oauth2" }
}
```

## Build & Test

```bash
# Install Python SDK
pip install a2a-sdk

# Run lint
./scripts/lint.sh

# Build docs
./scripts/build_docs.sh

# Run tests
pytest tests/
```

## Project Structure
```
Openclaw-A2A/
├── specification/     # A2A proto files
├── skills/           # OpenClaw skill templates for A2A work
├── scripts/          # Build, deploy, audit scripts
├── audit/            # Trace and audit tooling
├── examples/         # Usage examples
└── docs/             # A2A documentation
```

## Security Rules
- No exfiltration of credentials or private keys
- All API keys via environment variables, never hardcoded
- Audit logs for all agent-to-agent communications
- No modifying other agents' configs (will crash them)
