"""
OpenClaw A2A — Agent Card Generator

Auto-generates A2A Agent Cards from OpenClaw's local configuration.
Reads installed skills from ~/.openclaw/skills/ and builds
a complete AgentCard with capabilities, skills, and provider info.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from openclawa2a.models import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
)

# Default paths
DEFAULT_OPENCLAW_DIR = Path.home() / ".openclaw"
DEFAULT_SKILLS_DIR = DEFAULT_OPENCLAW_DIR / "skills"
DEFAULT_CONFIG_PATH = DEFAULT_OPENCLAW_DIR / "config.json"
DEFAULT_IDENTITY_PATH = DEFAULT_OPENCLAW_DIR / "workspace" / "IDENTITY.md"


class AgentCardBuilder:
    """
    Builds an AgentCard from OpenClaw's local environment.

    Usage:
        builder = AgentCardBuilder()
        card = builder.build()
    """

    def __init__(
        self,
        openclaw_dir: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
    ) -> None:
        self.openclaw_dir = Path(openclaw_dir) if openclaw_dir else DEFAULT_OPENCLAW_DIR
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR

    # ── Identity ───────────────────────────────────────────────────────────────

    def _load_identity(self) -> dict[str, str]:
        """Load IDENTITY.md as a simple key-value store."""
        identity: dict[str, str] = {}
        path = self.openclaw_dir / "workspace" / "IDENTITY.md"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if ": " in line:
                    key, val = line.split(": ", 1)
                    identity[key.strip()] = val.strip()
        return identity

    def _load_config(self) -> dict[str, Any]:
        """Load config.json if present."""
        path = self.openclaw_dir / "config.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    # ── Skills ─────────────────────────────────────────────────────────────────

    def _load_skill(self, skill_path: Path) -> Optional[AgentSkill]:
        """Load a single skill from its directory."""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")
            lines = content.splitlines()

            name = skill_path.name
            description = ""
            tags: list[str] = []
            metadata: dict[str, Any] = {}
            version = "1.0.0"

            # Simple frontmatter-style parse
            in_frontmatter = False
            frontmatter: dict[str, str] = {}

            for line in lines:
                stripped = line.strip()
                if stripped == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter and ": " in stripped:
                    k, v = stripped.split(": ", 1)
                    v = v.strip().strip("'\"")
                    frontmatter[k.strip()] = v

            # Parse frontmatter
            name = frontmatter.get("name", name)
            description = frontmatter.get("description", "")
            version = frontmatter.get("version", version)
            if frontmatter.get("tags"):
                tags = [t.strip() for t in frontmatter["tags"].split(",")]
            if frontmatter.get("emoji"):
                metadata["emoji"] = frontmatter["emoji"]

            # Fallback: use first non-empty line as description
            if not description:
                for line in lines:
                    if line.strip() and not line.strip().startswith("#"):
                        description = line.strip()[:2000]
                        break

            return AgentSkill(
                id=f"openclaw:{name.lower().replace(' ', '-')}",
                name=name,
                description=description[:2000],
                tags=tags,
                metadata=metadata,
            )
        except Exception:
            return None

    def _load_skills(self) -> list[AgentSkill]:
        """Discover and load all installed skills."""
        skills: list[AgentSkill] = []

        if not self.skills_dir.exists():
            return skills

        for entry in self.skills_dir.iterdir():
            if not entry.is_dir():
                continue
            skill = self._load_skill(entry)
            if skill:
                skills.append(skill)

        return skills

    # ── Capabilities ────────────────────────────────────────────────────────────

    def _detect_capabilities(self) -> AgentCapabilities:
        """Detect capabilities from environment."""
        return AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=True,
            extensions=[],
        )

    # ── Provider ───────────────────────────────────────────────────────────────

    def _build_provider(self, identity: dict[str, str], config: dict[str, Any]) -> AgentProvider:
        """Build the AgentProvider from identity and config."""
        return AgentProvider(
            organization=identity.get("machine", identity.get("host", "openclaw")),
            name=identity.get("Name", "openclaw-agent"),
            url=config.get("url"),
            version=config.get("openclaw_version", "unknown"),
        )

    # ── Build ───────────────────────────────────────────────────────────────────

    def build(
        self,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        extra_skills: Optional[list[AgentSkill]] = None,
        extra_capabilities: Optional[AgentCapabilities] = None,
        organization: Optional[str] = None,
        **overrides: Any,
    ) -> AgentCard:
        """
        Build a fully-populated AgentCard.

        Values not provided are auto-detected from the OpenClaw environment.
        """
        identity = self._load_identity()
        config = self._load_config()
        skills = self._load_skills()

        if extra_skills:
            skills.extend(extra_skills)

        provider = AgentProvider(
            organization=organization
            or identity.get("machine", identity.get("host", "openclaw")),
            name=name or identity.get("Name", "openclaw-agent"),
            url=url or config.get("url"),
            version=config.get("openclaw_version", "unknown"),
        )

        return AgentCard(
            name=name or identity.get("Name", "openclaw-agent"),
            version=version or config.get("version", "1.0.0"),
            description=description
            or "OpenClaw agent powered by A2A protocol",
            provider=provider,
            capabilities=extra_capabilities or self._detect_capabilities(),
            skills=skills,
            interfaces=[AgentInterface(protocol="http://a2a-protocol.org", version="1.0.0")],
            url=url,
            metadata={
                "openclaw_dir": str(self.openclaw_dir),
                "hostname": identity.get("machine", "unknown"),
            },
        )

    def build_from_env(self) -> AgentCard:
        """
        Build an AgentCard using only environment variables.

        Keys (all optional):
            OPENCLAW_AGENT_NAME
            OPENCLAW_AGENT_VERSION
            OPENCLAW_AGENT_DESCRIPTION
            OPENCLAW_AGENT_URL
            OPENCLAW_ORGANIZATION
        """
        return self.build(
            name=os.environ.get("OPENCLAW_AGENT_NAME"),
            version=os.environ.get("OPENCLAW_AGENT_VERSION"),
            description=os.environ.get("OPENCLAW_AGENT_DESCRIPTION"),
            url=os.environ.get("OPENCLAW_AGENT_URL"),
            organization=os.environ.get("OPENCLAW_ORGANIZATION"),
        )
