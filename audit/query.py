#!/usr/bin/env python3
"""A2A Audit Log Query Interface"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import argparse

AUDIT_DIR = Path(__file__).parent / "logs"


def search_logs(
    agent: Optional[str] = None,
    task_id: Optional[str] = None,
    event_type: Optional[str] = None,
    date: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 50
):
    """Search audit logs with filters."""
    
    log_files = sorted(AUDIT_DIR.glob("a2a-audit-*.jsonl"))
    
    if date:
        log_files = [f for f in log_files if date in f.name]
    
    results = []
    
    for log_file in log_files:
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Apply filters
                if agent and agent not in [entry.get("source_agent"), entry.get("target_agent")]:
                    continue
                if task_id and entry.get("task_id") != task_id:
                    continue
                if event_type and entry.get("event_type") != event_type:
                    continue
                if since and entry.get("timestamp") < since:
                    continue
                    
                results.append(entry)
                
                if len(results) >= limit:
                    break
    
    return results


def print_entry(entry):
    ts = entry["timestamp"].split("T")[1][:12]
    src = entry["source_agent"]
    tgt = entry["target_agent"]
    evt = entry["event_type"]
    status = entry["status"]
    summary = entry.get("content_summary", "")[:50]
    
    print(f"[{ts}] {src} → {tgt} | {evt} | {status} | {summary}...")


def main():
    parser = argparse.ArgumentParser(description="Query A2A audit logs")
    parser.add_argument("--agent", help="Filter by agent name")
    parser.add_argument("--task-id", help="Filter by task ID")
    parser.add_argument("--event-type", help="Filter by event type")
    parser.add_argument("--date", help="Date string (YYYY-MM-DD)")
    parser.add_argument("--since", help="ISO timestamp start")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    
    args = parser.parse_args()
    
    results = search_logs(
        agent=args.agent,
        task_id=args.task_id,
        event_type=args.event_type,
        date=args.date,
        since=args.since,
        limit=args.limit
    )
    
    if not results:
        print("No results found.")
        return
    
    print(f"Found {len(results)} entries:\n")
    for entry in results:
        print_entry(entry)


if __name__ == "__main__":
    main()
