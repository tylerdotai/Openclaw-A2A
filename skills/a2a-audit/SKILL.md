# OpenClaw-A2A Audit Skill

Skill for audit and trace operations in the OpenClaw-A2A project.

## When to Use

- When you need to log agent-to-agent communications
- When reviewing what happened in a cross-agent task
- When debugging A2A communication failures
- When generating compliance reports

## Quick Start

```python
from audit import A2AAuditLogger

audit = A2AAuditLogger()

# Log an event
audit.log(
    event_type="task_created",
    source="hoss",
    target="dexter",
    task_id="uuid-here",
    content="Build the agent card generator module",
    status="pending"
)
```

## Log Event Types

| Event | When to Use |
|-------|-------------|
| `task_created` | New A2A task initiated |
| `task_updated` | Task status changed |
| `message_sent` | Message dispatched to another agent |
| `message_received` | Message received from another agent |
| `agent_discovered` | Fetched an agent card |
| `skill_invoked` | Cross-agent skill delegation |
| `error` | Any A2A protocol error |

## Querying Logs

```bash
# By agent
python3 audit/query.py --agent hoss --limit 20

# By task ID
python3 audit/query.py --task-id <uuid>

# By date
python3 audit/query.py --date 2026-04-05

# Errors only
python3 audit/query.py --event-type error
```

## Best Practices

1. **Always log task creation** with clear content description
2. **Log completion** with duration_ms in metadata
3. **Log errors** with full error details in metadata
4. **Use structured metadata** for searchability
5. **Rotate logs** — query tool handles date-based file rotation

## Metadata Conventions

```python
metadata = {
    "duration_ms": 12345,
    "error_type": "timeout",
    "retry_count": 2,
    "subagent_id": "builder-01",
    "skill_used": "sdk-implementation"
}
```
