"""Tests for openclawa2a.agent_card"""

import json
import tempfile
from pathlib import Path

import pytest

from openclawa2a.agent_card import AgentCardBuilder
from openclawa2a.models import AgentCard, AgentSkill


class TestAgentCardBuilder:
    def test_load_identity_missing(self):
        """Missing IDENTITY.md should not raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = AgentCardBuilder(
                openclaw_dir=Path(tmpdir),
                skills_dir=Path(tmpdir) / "skills",
            )
            identity = builder._load_identity()
            assert identity == {}

    def test_load_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()
            (workspace / "IDENTITY.md").write_text(
                "Name: TestBot\nmachine: testhost\n"
            )
            builder = AgentCardBuilder(openclaw_dir=Path(tmpdir))
            identity = builder._load_identity()
            assert identity["Name"] == "TestBot"
            assert identity["machine"] == "testhost"

    def test_load_config_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = AgentCardBuilder(openclaw_dir=Path(tmpdir))
            config = builder._load_config()
            assert config == {}

    def test_load_config_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.json").write_text(
                json.dumps({"version": "2.0.0", "url": "https://example.com"})
            )
            builder = AgentCardBuilder(openclaw_dir=Path(tmpdir))
            config = builder._load_config()
            assert config["version"] == "2.0.0"
            assert config["url"] == "https://example.com"

    def test_load_skill_missing_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = AgentCardBuilder(skills_dir=Path(tmpdir) / "nonexistent")
            skills = builder._load_skills()
            assert skills == []

    def test_load_skill_from_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: My Skill\ndescription: Does things\ntags: a, b\nversion: 1.2.3\nemoji: '🤖'\n---\n\nDoes things for you."
            )
            builder = AgentCardBuilder(skills_dir=Path(tmpdir))
            skills = builder._load_skills()
            assert len(skills) == 1
            assert skills[0].name == "My Skill"
            assert skills[0].description == "Does things"
            assert "a" in skills[0].tags
            assert "b" in skills[0].tags
            assert skills[0].metadata["emoji"] == "🤖"

    def test_load_skill_fallback_description(self):
        """SKILL.md without frontmatter uses first non-heading line as description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "bare-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Bare Skill\n\nThis is the description.")
            builder = AgentCardBuilder(skills_dir=Path(tmpdir))
            skills = builder._load_skills()
            assert len(skills) == 1
            assert "This is the description" in skills[0].description

    def test_detect_capabilities(self):
        builder = AgentCardBuilder()
        caps = builder._detect_capabilities()
        assert caps.streaming is True
        assert caps.state_transition_history is True

    def test_build_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = AgentCardBuilder(openclaw_dir=Path(tmpdir))
            card = builder.build(
                name="TestAgent",
                version="1.0.0",
                description="A test agent",
            )
            assert card.name == "TestAgent"
            assert card.version == "1.0.0"
            assert card.description == "A test agent"

    def test_build_with_extra_skills(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = AgentCardBuilder(openclaw_dir=Path(tmpdir))
            extra = AgentSkill(id="custom", name="Custom", description="Custom skill")
            card = builder.build(extra_skills=[extra])
            assert len(card.skills) >= 1
            assert any(s.id == "custom" for s in card.skills)

    def test_build_from_env(self):
        import os

        os.environ["OPENCLAW_AGENT_NAME"] = "EnvAgent"
        os.environ["OPENCLAW_AGENT_VERSION"] = "3.0.0"
        try:
            builder = AgentCardBuilder()
            card = builder.build_from_env()
            assert card.name == "EnvAgent"
            assert card.version == "3.0.0"
        finally:
            del os.environ["OPENCLAW_AGENT_NAME"]
            del os.environ["OPENCLAW_AGENT_VERSION"]

    def test_agent_id_property(self):
        from openclawa2a.models import AgentProvider

        provider = AgentProvider(organization="myorg")
        card = AgentCard(
            name="myagent",
            version="1.0",
            description="d",
            provider=provider,
        )
        assert card.agent_id == "myorg/myagent"
