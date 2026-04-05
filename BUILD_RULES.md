# Build Rules — OpenClaw-A2A

**How to build, test, lint, and publish OpenClaw-A2A**

[![Build Status](https://img.shields.io/badge/build-pipeline-%23ff6b00)](scripts/build.sh)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A580%25-brightgreen)](tests/)
[![PyPI](https://img.shields.io/badge/pypi-openclawa2a-%23ff6b00)](https://pypi.org/project/openclawa2a)

---

## Prerequisites

Before building OpenClaw-A2A from source, ensure your environment meets these requirements.

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.10 | 3.12 |
| Git | 2.38 | latest |
| pip | 23.0 | latest |
| RAM | 2 GB | 8 GB |
| Disk | 500 MB free | 1 GB free |

### Python Environment

OpenClaw-A2A uses **Python 3.10+** with **Pydantic v2**. We strongly recommend a virtual environment.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
# .\.venv\Scripts\Activate.ps1  # Windows PowerShell
```

### Required Tools

```bash
# Core build tools
pip install --upgrade pip setuptools wheel

# Linting and formatting
pip install ruff

# Testing
pip install pytest pytest-asyncio pytest-cov

# Type checking (optional but recommended)
pip install mypy
```

---

## Building from Source

### Standard Build

```bash
# Clone the repository
git clone https://github.com/tylerdotai/Openclaw-A2A.git
cd Openclaw-A2A

# Install the SDK in editable mode with dev dependencies
pip install -e "sdk/python/[dev]"

# Or install just the core SDK
pip install -e sdk/python/
```

### Using the Build Script

The `scripts/build.sh` script automates the full build pipeline:

```bash
bash scripts/build.sh all        # Full pipeline: deps → lint → test → audit → docs
bash scripts/build.sh deps       # Install dependencies only
bash scripts/build.sh lint       # Run ruff linter
bash scripts/build.sh test       # Run test suite
bash scripts/build.sh audit      # Run audit report
bash scripts/build.sh docs       # Build documentation
```

### SDK Package Structure

```
sdk/python/
├── pyproject.toml          # Package metadata and build config
├── openclawa2a/            # Public SDK package
│   ├── __init__.py
│   ├── client.py
│   ├── server.py
│   ├── models.py
│   ├── agent_card.py
│   ├── tracing.py
│   ├── audit.py
│   ├── exceptions.py
│   └── py.typed            # PEP 561 type marker
├── tests/                  # SDK unit tests
└── docs/                   # SDK documentation (Sphinx)
```

### Building Distribution Artifacts

```bash
# Source distribution
python -m build --sdist

# Wheel
python -m build --wheel

# Both
python -m build
```

Artifacts are written to `sdk/python/dist/`.

---

## Running Tests

### Test Requirements

Tests require the following additional packages:

```bash
pip install pytest pytest-asyncio pytest-cov httpx aioresponses
```

### Running the Test Suite

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=openclawa2a --cov-report=term-missing --cov-report=html

# Run a specific test file
pytest tests/test_client.py -v

# Run tests matching a pattern
pytest tests/ -v -k "test_send_task"
```

### Coverage Requirements

OpenClaw-A2A enforces a **minimum 80% line coverage** policy. If coverage falls below this threshold, the build fails.

```
---------- coverage: platform darwin, python 3.12.x ----------
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------------
openclawa2a/__init__.py     12      0   100%
openclawa2a/client.py        89      7    92%
openclawa2a/server.py       74      4    95%
openclawa2a/models.py       120     3    98%
...
------------------------------------------------------------
TOTAL                      540     48    91%

Required: 80%  Actual: 91%  ✓ PASS
```

### Continuous Testing

Run tests in watch mode during development:

```bash
pip install pytest-watch
pytest-watch --cov=openclawa2a
```

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_client.py           # A2AClient tests
├── test_server.py           # A2AServer tests
├── test_models.py           # Pydantic model tests
├── test_agent_card.py       # AgentCard tests
├── test_audit.py            # AuditLogger tests
└── test_tracing.py          # Tracing integration tests
```

### Writing Tests

Use the shared fixtures from `conftest.py`:

```python
import pytest
from openclawa2a import A2AClient, AgentCard

@pytest.fixture
def agent_card():
    return AgentCard(
        name="test-agent",
        version="1.0.0",
        endpoint="http://localhost:18789/a2a"
    )

@pytest.fixture
def client(agent_card):
    return A2AClient(agent_card=agent_card)

def test_task_creation(client):
    task = client.create_task(input={"prompt": "test"})
    assert task.id is not None
    assert task.status == "pending"
```

---

## CI/CD Pipeline

OpenClaw-A2A uses a multi-stage CI/CD pipeline. The build script (`scripts/build.sh`) is the single source of truth for local builds; CI automation runs the equivalent stages.

### Pipeline Stages

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Checkout  │───▶│  Install     │───▶│   Lint      │───▶│   Test      │
│             │    │  Deps        │    │  (ruff)     │    │  (pytest)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                               │
       ┌────────────────────────────────────────────────────────┘
       ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Audit     │───▶│   Docs      │───▶│  Publish    │───▶│  Complete   │
│   Report    │    │  Build      │    │  (on tag)   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Stage Details

| Stage | Tool | Exit on Failure |
|-------|------|-----------------|
| Install | `pip install -e sdk/python/[dev]` | Yes |
| Lint | `ruff check .` | Yes |
| Test | `pytest tests/ --cov` | Yes |
| Audit | `python audit/query.py` (smoke) | No |
| Docs | `mkdocs build` | No |
| Publish | `twine upload dist/*` | Yes (tag only) |

### GitHub Actions (Planned)

GitHub Actions workflow at `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e "sdk/python/[dev]"
      - run: ruff check .
      - run: pytest tests/ -v --cov=openclawa2a --cov-fail-under=80
      - run: bash scripts/build.sh audit
```

---

## Pre-Commit Hooks

We use [`pre-commit`](https://pre-commit.com/) to run checks before every commit. This catches issues before they reach CI.

### Installation

```bash
pip install pre-commit
pre-commit install
```

### Configuration

The `.pre-commit-config.yaml` file defines all hooks:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: ruff check .
        language: system
        types: [python]

      - id: ruff-format
        name: ruff format (check)
        entry: ruff format --check .
        language: system
        types: [python]

      - id: mypy
        name: mypy type check
        entry: mypy openclawa2a/
        language: system
        types: [python]
        pass_filenames: false

      - id: pytest
        name: pytest (fast)
        entry: pytest tests/ -v --ignore=tests/integration/
        language: system
        pass_filenames: false
        stages: [push]  # Skip on commit, run on push only
```

### Manual Pre-Commit Run

```bash
# Run all hooks against all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff-check --all-files
```

### Hooks That Run on Every Commit

- `ruff check` — Import sorting, unused imports, style violations
- `ruff format --check` — Code formatting consistency
- `mypy` — Type checking (fails on type errors)

### Hooks That Run on Push Only

- `pytest` — Fast unit test subset (skips slow integration tests)

---

## Publishing the SDK

### PyPI Publishing

OpenClaw-A2A is published to [PyPI](https://pypi.org/project/openclawa2a) via `twine`.

#### Prerequisites

```bash
pip install build twine
```

#### Step 1: Version Bump

OpenClaw-A2A uses **inline version management** in `sdk/python/openclawa2a/_version.py`:

```bash
# Edit version
vim sdk/python/openclawa2a/_version.py
# Bump: __version__ = "1.2.3"
```

#### Step 2: Build Artifacts

```bash
cd sdk/python
rm -rf dist/ build/ *.egg-info
python -m build
```

#### Step 3: Verify Artifacts

```bash
twine check dist/*
```

#### Step 4: Upload to PyPI

**Test (recommended before production):**

```bash
twine upload --repository testpypi dist/*
```

**Production:**

```bash
twine upload dist/*
```

You will be prompted for your PyPI API token. Set up credentials in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-XXXXXXXXXXXXXXXXXXXX
```

### GitHub Release Workflow

1. Tag the release:
   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```
2. GitHub Actions detects the tag and runs the publish job.
3. The `publish` job builds the package and uploads to PyPI.

### npm Publishing (Planned)

A TypeScript/JS SDK is planned. When available, it will be published to npm:

```bash
cd sdk/javascript
npm login
npm publish --access public
```

---

## Deploying Documentation

### MkDocs Setup

Documentation is built with [MkDocs](https://www.mkdocs.org/) and the Material theme.

```bash
pip install mkdocs mkdocs-material
```

### Local Docs Preview

```bash
mkdocs serve
# Opens at http://localhost:8000
```

### Building Docs

```bash
mkdocs build
# Output to site/
```

### Deploying to GitHub Pages

```bash
mkdocs gh-deploy
```

This builds the docs and pushes to the `gh-pages` branch.

### Docs Structure

```
docs/
├── index.md                  # Landing page
├── specification.md           # A2A protocol spec
├── roadmap.md                # Project roadmap
├── topics/                   # Conceptual docs
│   ├── what-is-a2a.md
│   ├── a2a-and-mcp.md
│   ├── agent-discovery.md
│   └── streaming-and-async.md
├── tutorials/                # Step-by-step guides
│   └── python/
│       ├── 1-introduction.md
│       └── ...
├── sdk/                      # SDK reference
│   ├── index.md
│   └── python.md
└── assets/                   # Images and diagrams
```

### Customizing the Theme

The orange brand accent (`#ff6b00`) is configured in `docs/stylesheets/custom.css`:

```css
:root {
  --md-primary-fg-color: #ff6b00;
  --md-primary-fg-color--light: #ff8533;
  --md-primary-fg-color--dark: #cc5500;
}
```

---

## Dependency Management

### Updating Dependencies

```bash
# Check for outdated packages
pip list --outdated

# Update all packages
pip install -U -r sdk/python/requirements.txt
```

### Locking Versions

For reproducible builds, use `pip-tools`:

```bash
pip install pip-tools
pip-compile sdk/python/pyproject.toml
pip-compile sdk/python/dev-requirements.in
```

This generates `requirements.txt` and `dev-requirements.txt` with pinned versions.

---

## Release Checklist

Before each release:

- [ ] Run `bash scripts/build.sh all` locally
- [ ] Verify coverage ≥ 80%
- [ ] Update `CHANGELOG.md`
- [ ] Bump version in `_version.py`
- [ ] Update this `BUILD_RULES.md` if any process changed
- [ ] Open a PR, get review
- [ ] Merge to `main`
- [ ] Tag the release: `git tag vX.Y.Z && git push --tags`
- [ ] Verify PyPI upload succeeded
- [ ] Verify docs deployed to GitHub Pages

---

## Support

For build and release questions, open a [GitHub Discussion](https://github.com/tylerdotai/Openclaw-A2A/discussions) or file an issue.
