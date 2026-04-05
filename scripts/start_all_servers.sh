#!/bin/bash
# A2A Multi-Agent Server Health Check & Restart — batched, non-blocking
# Checks all three A2A agent servers and starts missing ones

WORKSPACE="/home/tyler/.openclaw/workspace/Openclaw-A2A"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"

check_server() {
  local port=$1
  local name=$2
  # Use /agent-card as health check — returns JSON if server is up
  curl -sf "http://localhost:$port/agent-card" > /dev/null 2>&1 && echo "[$name] ✓ running on port $port" && return 0
  return 1
}

start_server() {
  local port=$1
  local name=$2
  local pid_file="$LOG_DIR/$name.pid"
  
  echo "[$name] Starting on port $port..."
  nohup python3 "$WORKSPACE/scripts/a2a_task_router.py" \
    --agent "$name" \
    > "$LOG_DIR/$name.log" 2>&1 &
  
  echo $! > "$pid_file"
  sleep 3
  
  if check_server "$port" "$name"; then
    echo "[$name] ✓ Started (PID: $(cat $pid_file))"
    return 0
  else
    echo "[$name] ✗ Failed — check $LOG_DIR/$name.log"
    tail -5 "$LOG_DIR/$name.log" 2>/dev/null
    return 1
  fi
}

echo "=== A2A Server Status ==="
all_running=true

check_server 8080 "dexter" || all_running=false
check_server 8081 "hoss" || all_running=false
check_server 8082 "brad" || all_running=false

if $all_running; then
  echo ""
  echo "All servers healthy. No restart needed."
  exit 0
fi

echo ""
echo "=== Starting Missing Servers ==="
echo ""

# Only start ports that aren't running
if ! curl -sf "http://localhost:8080/agent-card" > /dev/null 2>&1; then
  start_server 8080 "dexter"
fi

if ! curl -sf "http://localhost:8081/agent-card" > /dev/null 2>&1; then
  start_server 8081 "hoss"
fi

if ! curl -sf "http://localhost:8082/agent-card" > /dev/null 2>&1; then
  start_server 8082 "brad"
fi

echo ""
echo "=== Final Status ==="
check_server 8080 "dexter" || true
check_server 8081 "hoss" || true
check_server 8082 "brad" || true
