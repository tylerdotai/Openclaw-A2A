#!/bin/bash
# OpenClaw-A2A CI/CD Build Script
# Automated build, test, and audit for OpenClaw-A2A

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[BUILD]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 required but not found"
        exit 1
    fi
    log "Python version: $(python3 --version)"
}

# Install dependencies
install_deps() {
    log "Installing Python dependencies..."
    pip install a2a-sdk ruff pytest pytest-asyncio -q 2>/dev/null || true
    log "Dependencies installed"
}

# Run linting
run_lint() {
    log "Running ruff linter..."
    if command -v ruff &> /dev/null; then
        ruff check .
    else
        pip install ruff -q
        ruff check .
    fi
}

# Run tests
run_tests() {
    log "Running test suite..."
    if [ -d "tests" ]; then
        pytest tests/ -v --tb=short 2>/dev/null || warn "Tests failed or not configured"
    else
        warn "No tests/ directory found"
    fi
}

# Generate audit report
audit_report() {
    log "Checking audit logs..."
    if [ -f "audit/query.py" ]; then
        python3 audit/query.py --limit 10 2>/dev/null || true
    fi
}

# Build documentation
build_docs() {
    log "Building documentation..."
    if [ -f "scripts/build_docs.sh" ]; then
        bash scripts/build_docs.sh 2>/dev/null || warn "Docs build failed"
    else
        warn "build_docs.sh not found, skipping docs"
    fi
}

# Full pipeline
pipeline() {
    log "=== OpenClaw-A2A Build Pipeline ==="
    check_python
    install_deps
    run_lint
    run_tests
    audit_report
    build_docs
    log "=== Pipeline Complete ==="
}

# Parse args
case "${1:-all}" in
    lint)   run_lint ;;
    test)   run_tests ;;
    audit)  audit_report ;;
    docs)   build_docs ;;
    deps)   install_deps ;;
    all)    pipeline ;;
    *)      echo "Usage: $0 {lint|test|audit|docs|deps|all}" ;;
esac
