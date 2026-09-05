"""Auto mode: keys present -> commercial service; keys absent -> local.
The core promise: zero configuration either way."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from llm_providers import resolve_provider  # noqa: E402
from providers_common import has_key  # noqa: E402

ALL_KEY_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY")


def _clear(*extra):
    """Pop LLM_PROVIDER and every commercial key from the env."""
    for var in ("LLM_PROVIDER", *ALL_KEY_VARS, *extra):
        os.environ.pop(var, None)


class TestHasKey:
    def test_real_value_counts(self):
        with patch.dict(os.environ, {"SOME_KEY": "sk-ant-abc123"}):
            assert has_key("SOME_KEY")

    def test_empty_and_missing_do_not_count(self):
        with patch.dict(os.environ, {"SOME_KEY": "  "}):
            assert not has_key("SOME_KEY")
        os.environ.pop("NOT_SET_KEY", None)
        assert not has_key("NOT_SET_KEY")

    def test_env_example_placeholders_do_not_count(self):
        """Copying .env.example untouched must not look like having keys."""
        for placeholder in (
            "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "APIxxxxxxxxxxxxxxxxx",
            "wss://your-project.livekit.cloud",
        ):
            with patch.dict(os.environ, {"SOME_KEY": placeholder}):
                assert not has_key("SOME_KEY"), f"placeholder counted as real: {placeholder}"


class TestLLMAutoMode:
    def test_each_key_selects_its_provider(self):
        expected = {
            "ANTHROPIC_API_KEY": "anthropic",
            "OPENAI_API_KEY": "openai",
            "GOOGLE_API_KEY": "google",
            "GROQ_API_KEY": "groq",
        }
        for var, provider in expected.items():
            with patch.dict(os.environ, {}, clear=False):
                _clear()
                os.environ[var] = "a-real-looking-key-123"
                assert resolve_provider() == provider, f"{var} should select {provider}"

    def test_quality_order_anthropic_wins(self):
        with patch.dict(os.environ, {}, clear=False):
            _clear()
            os.environ["GROQ_API_KEY"] = "gsk_real123"
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-real123"
            assert resolve_provider() == "anthropic"

    def test_no_keys_means_local(self):
        with patch.dict(os.environ, {}, clear=False):
            _clear()
            assert resolve_provider() == "ollama"

    def test_explicit_provider_beats_keys(self):
        """A user who SET a provider gets that provider, keys or not."""
        with patch.dict(os.environ, {}, clear=False):
            _clear()
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-real123"
            os.environ["LLM_PROVIDER"] = "ollama"
            assert resolve_provider() == "ollama"

    def test_placeholder_key_still_means_local(self):
        with patch.dict(os.environ, {}, clear=False):
            _clear()
            os.environ["GROQ_API_KEY"] = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            assert resolve_provider() == "ollama"
