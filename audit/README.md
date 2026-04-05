# Audit & Trace Module

Production-ready audit logging for A2A agent communications.

## Overview

Every agent-to-agent message in the Hydra Mesh A2A implementation is logged for:
- **Traceability:** Track task delegation and completion
- **Auditing:** Record who did what and when
- **Debugging:** Reconstruct conversation flow when things break
- **Compliance:** Meet production hardening requirements

## Log Schema

Each A2A event produces a structured log entry:

```json
{
  "timestamp": "2026-04-05T03:34:00.000Z",
  "event_type": "task_created|task_updated|message_sent|agent_discovered|error",
  "source_agent": "hoss|dexter|brad|subagent:name",
  "target_agent": "hoss|dexter|brad|*",
  "task_id": "uuid",
  "message_id": "uuid",
  "content_summary": "first 200 chars of message",
  "status": "pending|in_progress|completed|failed|cancelled",
  "duration_ms": 1234,
  "metadata": {}
}
```

## Event Types

| Event | Description |
|-------|-------------|
| `task_created` | New A2A task initiated |
| `task_updated` | Task state changed |
| `message_sent` | A2A message dispatched |
| `message_received` | A2A message received |
| `agent_discovered` | Agent card fetched |
| `skill_invoked` | Cross-agent skill call |
| `error` | Communication or protocol error |

## Implementation

### Python Audit Logger

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

class A2AAuditLogger:
    def __init__(self, log_dir: str = "audit/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("a2a.audit")
        
    def log(self, event_type: str, source: str, target: str,
            task_id: str = None, message_id: str = None,
            content: str = "", status: str = "pending",
            metadata: dict = None):
        
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "source_agent": source,
            "target_agent": target,
            "task_id": task_id or str(uuid4()),
            "message_id": message_id or str(uuid4()),
            "content_summary": content[:200] if content else "",
            "status": status,
            "metadata": metadata or {}
        }
        
        # Write to rolling log file
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"a2a-audit-{date_str}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        self.logger.info(f"[{event_type}] {source} → {target}: {status}")
        return entry
```

### Usage in OpenClaw Agent

```python
from audit import A2AAuditLogger

audit = A2AAuditLogger()

# Log task creation
audit.log(
    event_type="task_created",
    source="hoss",
    target="dexter",
    task_id=task.id,
    content="Build agent card generator for OpenClaw",
    status="pending"
)

# Log completion
audit.log(
    event_type="task_updated",
    source="dexter",
    target="hoss",
    task_id=task.id,
    status="completed",
    metadata={"duration_ms": 45230}
)
```

## Log Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Daily JSONL | 30 days | `audit/logs/` |
| Weekly summary | 90 days | `audit/summaries/` |
| Critical errors | 1 year | `audit/critical/` |

## Query Interface

```bash
# Search logs by agent
python3 audit/query.py --agent hoss --date 2026-04-05

# Search by task ID
python3 audit/query.py --task-id <uuid>

# Error report
python3 audit/query.py --event-type error --since 2026-04-01
```

## Audit Checklist

For each A2A task:
- [ ] Task created with proper description
- [ ] Delegation logged (source → target)
- [ ] Status updates logged
- [ ] Completion or error logged
- [ ] Duration recorded
