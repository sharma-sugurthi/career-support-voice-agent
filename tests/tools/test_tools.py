"""Tests for the research/finance tools - offline, no network calls."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from tools.fetch import extract_readable, is_allowed, robots_url_for  # noqa: E402
from tools.finance import compute_budget  # noqa: E402
from tools.search import _normalize, resolve_search_provider  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestSearchProviderSelection:
    def test_default_is_keyless(self):
        import os
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEARCH_PROVIDER", None)
            assert resolve_search_provider() == "ddgs", (
                "The default search must work without any API key"
            )

    def test_optional_providers_resolve(self):
        import os
        for provider in ("tavily", "brave", "ddgs"):
            with patch.dict(os.environ, {"SEARCH_PROVIDER": provider}):
                assert resolve_search_provider() == provider

    def test_unknown_provider_raises(self):
        import os
        with patch.dict(os.environ, {"SEARCH_PROVIDER": "askjeeves"}):
            with pytest.raises(ValueError, match="Unknown SEARCH_PROVIDER"):
                resolve_search_provider()

    def test_results_are_normalized_with_url(self):
        """The citation contract: every result must carry its URL."""
        r = _normalize("  Title ", " https://ex.am/page ", "x" * 900)
        assert r["title"] == "Title"
        assert r["url"] == "https://ex.am/page"
        assert len(r["snippet"]) <= 500
        assert set(r.keys()) == {"title", "url", "snippet"}


class TestFetch:
    def test_robots_url(self):
        assert (
            robots_url_for("https://example.com/a/b?q=1")
            == "https://example.com/robots.txt"
        )

    def test_robots_disallow_respected(self):
        robots = "User-agent: *\nDisallow: /private/"
        assert is_allowed(robots, "https://ex.am/public/page") is True
        assert is_allowed(robots, "https://ex.am/private/page") is False

    def test_extract_readable_strips_boilerplate(self):
        html = (
            "<html><head><script>evil()</script></head><body>"
            "<article><p>GATE 2027 applications open in September.</p>"
            "<p>The fee is 1800 rupees for general category candidates.</p></article>"
            "</body></html>"
        )
        text = extract_readable(html)
        assert "GATE 2027" in text
        assert "evil()" not in text

    def test_non_http_rejected(self):
        from tools.fetch import fetch_url
        with pytest.raises(ValueError, match="http"):
            _run(fetch_url("file:///etc/passwd"))


class TestBudget:
    def test_totals_exactly(self):
        result = compute_budget(
            [
                {"label": "tuition", "amount": 1200000},
                {"label": "living", "amount": 480000.50},
                {"label": "visa", "amount": 12000},
            ]
        )
        assert result["total"] == 1692000.50
        assert result["count"] == 3

    def test_malformed_item_raises(self):
        with pytest.raises(ValueError, match="malformed"):
            compute_budget([{"label": "x", "amount": "a lot"}])

    def test_empty_budget(self):
        assert compute_budget([]) == {"total": 0.0, "items": [], "count": 0}


class TestSameCurrency:
    def test_no_network_needed_for_identity_conversion(self):
        from tools.finance import convert_currency
        result = _run(convert_currency(100, "inr", "INR"))
        assert result["converted"] == 100.0
        assert result["rate"] == 1.0


class TestAgentToolWiring:
    """Least privilege: each agent gets only its allowlisted tools."""

    def _tool_names(self, agent) -> set:
        names = set()
        for tool in agent.tools:
            info = getattr(tool, "info", None)
            names.add(info.name if info else getattr(tool, "__name__", str(tool)))
        return names

    def test_coach_tools(self):
        from agents_team import CareerCoach
        names = self._tool_names(CareerCoach())
        assert {"web_search", "save_plan", "get_plans", "remember", "forget"} <= names

    def test_specialists_have_search_and_save(self):
        from agents_team import InterviewCoach, ResumeCoach
        for cls in (ResumeCoach, InterviewCoach):
            names = self._tool_names(cls())
            assert {"web_search", "save_plan"} <= names, f"{cls.__name__} missing tools"
            assert "get_plans" not in names, (
                f"{cls.__name__} should not have get_plans (least privilege)"
            )

    def test_failure_messages_forbid_guessing(self):
        """When a tool fails, the model must be told NOT to guess."""
        import inspect
        from tools import agent_tools
        src = inspect.getsource(agent_tools)
        assert src.lower().count("do not guess") >= 2
        assert "do not invent" in src.lower()
