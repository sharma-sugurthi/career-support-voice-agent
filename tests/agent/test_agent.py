"""
Tests for the Career Support Voice Agent.

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
            "CARTESIA_API_KEY",
            "LLM_PROVIDER",
        }
        missing = required - env.keys()
        assert not missing, f".env.example is missing keys: {missing}"

    def test_env_example_defaults_to_self_hosted(self):
        """The out-of-the-box config must not require any LLM API key."""
        env = _load_env_example()
        assert env.get("LLM_PROVIDER") == "ollama", (
            "LLM_PROVIDER in .env.example should default to the self-hosted "
            "'ollama' provider"
        )

    def test_env_local_exists(self):
        """The actual secrets file must exist for the agent to run locally."""
        if not (AGENT_DIR / ".env.local").exists():
            pytest.skip(
                ".env.local not present (fine for CI) - copy .env.example "
                "and fill in credentials to run the agent"
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
        if not (AGENT_DIR / ".venv").exists():
            pytest.skip("Virtual environment not found - run: uv sync")

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
# The coach agent (entry agent of the team; deeper team tests in test_team.py)
# ---------------------------------------------------------------------------

class TestCoachAgent:
    def _get_coach_class(self):
        from agents_team import CareerCoach
        return CareerCoach

    def test_coach_is_agent_subclass(self):
        from livekit.agents import Agent
        assert issubclass(self._get_coach_class(), Agent)

    def test_coach_instructions_are_general(self):
        """The prompt must serve any user, not one institute."""
        instructions = self._get_coach_class()().instructions
        assert "career" in instructions.lower(), (
            "Agent instructions must describe career coaching"
        )
        assert "RGUKT" not in instructions, (
            "Agent instructions still mention RGUKT - the project pivoted to "
            "a general-purpose career agent"
        )

    def test_coach_instructions_no_markdown(self):
        """Voice agents should never use markdown formatting in their prompts."""
        instructions = self._get_coach_class()().instructions
        assert "asterisks" in instructions.lower() or "formatting" in instructions.lower(), (
            "Instructions should explicitly prohibit markdown/formatting for voice output"
        )

    def test_memory_context_lands_in_instructions(self):
        coach = self._get_coach_class()(memory_context="Known: target role is data analyst")
        assert "data analyst" in coach.instructions


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
            "livekit-plugins-anthropic",
            "livekit-plugins-assemblyai",
            "livekit-plugins-cartesia",
            "livekit-plugins-openai",
            "python-dotenv",
        ]
        for prefix in required_prefixes:
            assert prefix in deps, (
                f"Dependency '{prefix}' missing from pyproject.toml"
            )


# ---------------------------------------------------------------------------
# LLM Provider Selection
# ---------------------------------------------------------------------------

class TestLLMProviders:
    """llm_providers.py has no import-time plugin dependencies, so these run
    without any LiveKit plugin installed."""

    def _module(self):
        import llm_providers
        return llm_providers

    def test_default_provider_is_self_hosted(self):
        mod = self._module()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_PROVIDER", None)
            assert mod.resolve_provider() == "ollama"

    def test_all_supported_providers_resolve(self):
        mod = self._module()
        for provider in mod.SUPPORTED_PROVIDERS:
            with patch.dict(os.environ, {"LLM_PROVIDER": provider}):
                assert mod.resolve_provider() == provider

    def test_unknown_provider_raises(self):
        mod = self._module()
        with patch.dict(os.environ, {"LLM_PROVIDER": "does-not-exist"}):
            with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
                mod.resolve_provider()

    def test_every_provider_has_a_default_model(self):
        mod = self._module()
        for provider in mod.SUPPORTED_PROVIDERS:
            assert mod.DEFAULT_MODELS.get(provider), (
                f"No default model configured for provider '{provider}'"
            )

    def test_llm_model_env_overrides_default(self):
        mod = self._module()
        with patch.dict(os.environ, {"LLM_MODEL": "my-custom-model"}):
            assert mod.resolve_model("ollama") == "my-custom-model"

    def test_openai_compatible_requires_base_url(self):
        mod = self._module()
        env = {"LLM_PROVIDER": "openai-compatible"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LLM_BASE_URL", None)
            with pytest.raises(ValueError, match="LLM_BASE_URL"):
                mod.create_llm()


class TestLLMErrorClassification:
    """The agent must SAY when credits run out or a rate limit hits."""

    def _classify(self, text):
        import llm_providers
        return llm_providers.classify_llm_error(Exception(text))

    def test_quota_errors_detected(self):
        samples = [
            "Error code: 429 - insufficient_quota: You exceeded your current quota",
            "Your credit balance is too low to access the Anthropic API",
            "402 Payment Required",
        ]
        for text in samples:
            assert self._classify(text) == "quota", f"not classified as quota: {text}"

    def test_rate_limit_errors_detected(self):
        samples = [
            "Rate limit reached for model, please try again in 20s",
            "429 Too Many Requests",
            "Overloaded",
        ]
        for text in samples:
            assert self._classify(text) == "rate_limit", (
                f"not classified as rate_limit: {text}"
            )

    def test_unrelated_errors_return_none(self):
        assert self._classify("connection reset by peer") is None

    def test_spoken_messages_exist_for_all_classifications(self):
        import llm_providers
        assert "quota" in llm_providers.SPOKEN_ERROR_MESSAGES
        assert "rate_limit" in llm_providers.SPOKEN_ERROR_MESSAGES
        assert "completed" in llm_providers.SPOKEN_ERROR_MESSAGES["quota"].lower()
        assert "wait" in llm_providers.SPOKEN_ERROR_MESSAGES["rate_limit"].lower()
