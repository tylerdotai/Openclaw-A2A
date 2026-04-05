# OpenClaw A2A Coordination System

## Overview

Three OpenClaw agents (Hoss, Brad, Dexter) coordinate via A2A protocol while maintaining their distinct roles. Each agent manages sub-agents and collaborates through defined communication patterns.

---

## C-Suite Division of Labor

### Hoss — Chief Execution Officer (CEO)
- **Primary:** Execution, coordination, memory maintenance
- **Focus:** Flume SaaS Factory operations, wiki maintenance, system architecture
- **Sub-agents:** builder, coder, devops, einstein, marketer, ops, sales, scout

### Dexter — Chief Technology Officer (CTO)
- **Primary:** Technical implementation, infrastructure, A2A protocol development
- **Focus:** clawbox (128GB AMD Ryzen), OpenClaw gateway, local LLM integration, Qdrant RAG
- **Sub-agents:** (spawns as needed for technical tasks)

### Brad — Chief Infrastructure Officer (CIO)
- **Primary:** Lightweight orchestration, watchdog services, cross-server monitoring
- **Focus:** Pi 4 backup, health monitoring, wiki curation, legacy systems
- **Sub-agents:** (minimal, Pi-constrained)

---

## A2A Communication Protocol

### Agent Cards

Each agent exposes an Agent Card for discovery:

```
GET /agents/{agent-id}/card
```

**Hoss Card:** `http://192.168.0.28:18789/agents/hoss/card`
**Dexter Card:** `http://clawbox:18789/agents/dexter/card`
**Brad Card:** `http://192.168.0.221:18789/agents/brad/card`

### Task Delegation via A2A

When Hoss delegates to Dexter:

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "skill": "code-review",
    "input": {
      "task": "Review auth module for security vulnerabilities",
      "repo": "tylerdotai/faireplay",
      "files": ["src/auth/**/*.ts"]
    },
    "agentId": "dexter"
  }
}
```

### Sub-Agent Coordination

Each C-suite agent can spawn sub-agents. Sub-agents communicate upward:

```
Dexter (sub-agent) → Dexter (parent) → Hoss (C-suite) → Dexter (peer)
```

### Message Format

All A2A messages follow JSON-RPC 2.0:

```json
{
  "jsonrpc": "2.0",
  "id": "unique-message-id",
  "method": "tasks/send",
  "params": {
    "skill": "string",
    "input": {},
    "context": {
      "from": "hoss|dexter|brad",
      "replyTo": "channel-id",
      "urgent": false
    }
  }
}
```

---

## Coordination Rules

### 1. No Overlapping Work
- Hoss maintains task registry in `memory/task-registry.md`
- Before starting work, check registry for conflicts
- Post new tasks before starting: `→ #personal-intelligence`

### 2. Clear Delegation
- Tyler assigns to Hoss → Hoss delegates to Dexter/Brad → Hoss synthesizes
- Never delegate sideways without informing Hoss
- If Dexter needs something from Brad, ask Hoss to coordinate

### 3. Sub-Agent Discipline
- Each C-suite agent owns their sub-agent work
- Sub-agents report to parent agent, not directly to other C-suite
- Cross-sub-agent communication goes: sub → parent → other parent → their sub

### 4. Sync Points
- Morning: Hoss posts daily standup summary to `#personal-intelligence`
- Evening: Brad runs health check on all hosts
- As-needed: Cross-agent task handoffs via A2A messages

---

## Build Rules (Non-Negotiable)

All code must follow:

1. **TDD: 80% Coverage Minimum**
   - Write failing test FIRST
   - Run `npm test -- --coverage` before every PR
   - Coverage reports required before merge

2. **Industry Standards**
   - ESLint + Prettier formatting
   - TypeScript strict mode
   - No `any` types without justification

3. **Security: Zero Credential Leaks**
   - All secrets in `.env`, never committed
   - Use `process.env` for all sensitive values
   - No hardcoded tokens, keys, or internal URLs in public code

4. **GitHub Standards**
   - Follow `GITHUB_README_SKILL.md` for all README files
   - Commit messages: descriptive, not "fix stuff"
   - PRs require review from another agent

5. **Documentation**
   - Code + docs must match
   - Update docs when changing code
   - Public interfaces documented

---

## Shared Resources

### Infrastructure
| Host | IP | Agent | Purpose |
|------|-----|-------|---------|
| ClawBox | clawbox | Dexter | Primary compute (32 cores, 128GB), OpenClaw, SearXNG, Qdrant |
| Mac mini M4 | .28 | Hoss | Main agent, Flume, Terminal Portfolio, Autoresearch |
| Pi 4 | .221 | Brad | Lightweight monitoring, orchestration, backup |

### Brad Deliverables (CIO)
Brad's assigned work for this project:
- `audit/` — Audit logging module (see `audit/README.md`)
- `skills/openclaw-a2a-coordination/` — A2A project skill template
- `skills/a2a-audit/` — Audit/trace skill for agent communications
- `scripts/build.sh` — CI/CD pipeline (lint, test, audit, docs)
- `audit/query.py` — Query interface for audit logs

### Shared Services (on clawbox)
- **SearXNG:** `http://localhost:8888`
- **Qdrant:** `http://localhost:6333`
- **Ollama:** `http://localhost:11434`

### API Limits
- **MiniMax M2.7:** 4,500 req/5hrs (primary)
- **Local Ollama:** Unlimited (supplementary)

---

## Repository Access

- **Main repo:** `https://github.com/tylerdotai/Openclaw-A2A`
- **Credentials:** Use `gh` CLI (already authenticated as tylerdotai)
- **Branching:** `feature/*` for work, `main` for production

---

## Skills for This Project

Create project-specific skills in:
```
~/.openclaw/skills/openclaw-a2a/
```

Core skills needed:
- `a2a-client` — How to send A2A messages
- `a2a-server` — How to receive and respond to A2A messages
- `a2a-agent-card` — How to expose and query Agent Cards
- `coordination-protocol` — How to avoid overlap, delegate properly

---

_Last updated: 2026-04-05 by Hoss_