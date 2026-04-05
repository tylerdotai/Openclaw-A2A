"""A2A Audit Logger — Production-ready trace logging for agent communications"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional

AUDIT_VERSION = "1.0.0"


class A2AAuditLogger:
    """Structured audit logger for A2A agent-to-agent communications."""
    
    def __init__(self, log_dir: str = "audit/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("a2a.audit")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    
    def log(
        self,
        event_type: str,
        source: str,
        target: str,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None,
        content: str = "",
        status: str = "pending",
        metadata: Optional[dict] = None
    ) -> dict:
        """Log an A2A event.
        
        Args:
            event_type: Type of event (task_created, task_updated, message_sent, etc.)
            source: Source agent identifier
            target: Target agent identifier
            task_id: Optional task ID
            message_id: Optional message ID
            content: Human-readable content summary
            status: Event status (pending, in_progress, completed, failed, cancelled)
            metadata: Additional structured metadata
        
        Returns:
            The log entry dict that was written
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": AUDIT_VERSION,
            "event_type": event_type,
            "source_agent": source,
            "target_agent": target,
            "task_id": task_id or str(uuid4()),
            "message_id": message_id or str(uuid4()),
            "content_summary": content[:200] if content else "",
            "status": status,
            "metadata": metadata or {}
        }
        
        # Write to rolling daily log file
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"a2a-audit-{date_str}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        self.logger.info(
            f"[{event_type}] {source} → {target}: {status}"
        )
        
        return entry
    
    # Convenience methods
    
    def task_created(self, source: str, target: str, task_id: str, content: str, **kwargs):
        return self.log("task_created", source, target, task_id=task_id, content=content, **kwargs)
    
    def task_updated(self, source: str, target: str, task_id: str, status: str, **kwargs):
        return self.log("task_updated", source, target, task_id=task_id, status=status, **kwargs)
    
    def message_sent(self, source: str, target: str, message_id: str, content: str = "", **kwargs):
        return self.log("message_sent", source, target, message_id=message_id, content=content, **kwargs)
    
    def message_received(self, source: str, target: str, message_id: str, content: str = "", **kwargs):
        return self.log("message_received", source, target, message_id=message_id, content=content, **kwargs)
    
    def agent_discovered(self, source: str, target: str, content: str = "", **kwargs):
        return self.log("agent_discovered", source, target, content=content, **kwargs)
    
    def skill_invoked(self, source: str, target: str, skill_id: str, **kwargs):
        return self.log("skill_invoked", source, target, content=f"Skill: {skill_id}", **kwargs)
    
    def error(self, source: str, target: str, error: str, **kwargs):
        return self.log("error", source, target, status="failed", content=error, metadata={"error": error, **kwargs})
