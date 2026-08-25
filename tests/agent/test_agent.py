"""
Tests for the RGUKT Career Support Voice Agent.

These are integration-light tests - they verify the agent's structural
correctness (imports, configuration, class hierarchy) without requiring
live API credentials or an active LiveKit room.

Run with:
    cd livekit-voice-agent
    source .venv/bin/activate
    pytest ../../tests/agent/ -v
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the agent module importable from the tests directory
AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_env_example() -> dict[str, str]:
    """Parse the .env.example file into a dict, ignoring comments."""
    env_example = AGENT_DIR / ".env.example"
    result = {}
    for line in env_example.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Environment & Config
# ---------------------------------------------------------------------------

class TestEnvironmentSetup:
    def test_env_example_exists(self):
        assert (AGENT_DIR / ".env.example").exists(), (
            ".env.example is missing - new contributors won't know what to set"
        )

    def test_env_example_has_required_keys(self):
        env = _load_env_example()
        required = {
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
            "ASSEMBLYAI_API_KEY",
            "GROQ_API_KEY",
            "CARTESIA_API_KEY",
        }
        missing = required - env.keys()
        assert not missing, f".env.example is missing keys: {missing}"

    def test_env_local_exists(self):
        """The actual secrets file must exist for the agent to run."""
        assert (AGENT_DIR / ".env.local").exists(), (
            ".env.local not found - copy .env.example and fill in your credentials"
        )

    def test_env_local_not_committed(self):
        """.env.local must be gitignored so secrets don't leak into git."""
        gitignore = Path(__file__).parent.parent.parent / ".gitignore"
        content = gitignore.read_text()
        assert ".env.*" in content or ".env.local" in content, (
            ".env.local is not covered by .gitignore - this is a security risk"
        )


# ---------------------------------------------------------------------------
# Agent Module
# ---------------------------------------------------------------------------

class TestAgentModule:
    def test_agent_file_exists(self):
        assert (AGENT_DIR / "agent.py").exists()

    def test_pyproject_exists(self):
        assert (AGENT_DIR / "pyproject.toml").exists()

    def test_venv_exists(self):
        assert (AGENT_DIR / ".venv").exists(), (
            "Virtual environment not found - run: uv sync"
        )

    def test_required_packages_importable(self):
        """Core packages that must be importable before any agent starts."""
        packages = [
            "livekit",
            "livekit.agents",
            "openai",
            "dotenv",
        ]
        for pkg in packages:
            try:
                __import__(pkg)
            except ImportError:
                pytest.fail(f"Required package not importable: {pkg}")

    def test_agent_imports_without_error(self):
        """
        agent.py must be importable in isolation. We patch load_dotenv and
        AgentServer to avoid side effects (network connections, file I/O).
        """
        with (
            patch("dotenv.load_dotenv"),
            patch("livekit.agents.AgentServer", return_value=MagicMock()),
        ):
            import importlib
            import agent  # noqa: F401 - we just want the import to not raise
            importlib.reload(agent)


# ---------------------------------------------------------------------------
# Assistant Class
# ---------------------------------------------------------------------------

class TestAssistantClass:
    def _get_assistant_class(self):
        with (
            patch("dotenv.load_dotenv"),
            patch("livekit.agents.AgentServer", return_value=MagicMock()),
        ):
            import importlib
            import agent
            importlib.reload(agent)
            return agent.Assistant

    def test_assistant_is_agent_subclass(self):
        from livekit.agents import Agent
        Assistant = self._get_assistant_class()
        assert issubclass(Assistant, Agent), (
            "Assistant must subclass livekit.agents.Agent"
        )

    def test_assistant_has_instructions(self):
        Assistant = self._get_assistant_class()
        # Instantiate with mocked parent __init__
        with patch("livekit.agents.Agent.__init__", lambda self, **kw: None):
            instance = Assistant.__new__(Assistant)
            # Verify the class itself calls super().__init__ with instructions
            # by checking the source contains the keyword
            import inspect
            src = inspect.getsource(Assistant.__init__)
            assert "instructions" in src

    def test_assistant_instructions_mention_rgukt(self):
        """The system prompt must mention RGUKT to keep the agent on-brand."""
        Assistant = self._get_assistant_class()
        import inspect
        src = inspect.getsource(Assistant.__init__)
        assert "RGUKT" in src, (
            "Agent instructions don't mention RGUKT - the branding is missing"
        )

    def test_assistant_instructions_no_markdown(self):
        """Voice agents should never use markdown formatting in their prompts."""
        Assistant = self._get_assistant_class()
        import inspect
        src = inspect.getsource(Assistant.__init__)
        assert "asterisks" in src.lower() or "formatting" in src.lower(), (
            "Instructions should explicitly prohibit markdown/formatting for voice output"
        )


# ---------------------------------------------------------------------------
# pyproject.toml Integrity
# ---------------------------------------------------------------------------

class TestPyprojectIntegrity:
    def _load_toml(self) -> dict:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]
        with open(AGENT_DIR / "pyproject.toml", "rb") as f:
            return tomllib.load(f)

    def test_project_name_set(self):
        data = self._load_toml()
        assert data["project"]["name"], "pyproject.toml must have a project name"

    def test_python_version_constraint(self):
        data = self._load_toml()
        requires = data["project"].get("requires-python", "")
        assert requires, "pyproject.toml must specify requires-python"

    def test_required_dependencies_declared(self):
        data = self._load_toml()
        deps = " ".join(data["project"].get("dependencies", []))
        required_prefixes = [
            "livekit-agents",
            "livekit-plugins-assemblyai",
            "livekit-plugins-cartesia",
            "livekit-plugins-openai",
            "python-dotenv",
        ]
        for prefix in required_prefixes:
            assert prefix in deps, (
                f"Dependency '{prefix}' missing from pyproject.toml"
            )
