"""Tests for the SQLite memory store - pure Python, no live services."""
import sys
import time
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from memory.store import MemoryStore  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return MemoryStore(db_path=tmp_path / "test.db")


class TestUsers:
    def test_first_visit_is_not_returning(self, store):
        assert store.touch_user("user_abc") is False

    def test_second_visit_is_returning(self, store):
        store.touch_user("user_abc")
        assert store.touch_user("user_abc") is True

    def test_different_users_are_separate(self, store):
        store.touch_user("user_a")
        assert store.touch_user("user_b") is False


class TestFacts:
    def test_remember_and_recall(self, store):
        store.remember_fact("u1", "target_role", "data analyst")
        facts = store.get_facts("u1")
        assert len(facts) == 1
        assert facts[0]["key"] == "target_role"
        assert facts[0]["value"] == "data analyst"
        assert facts[0]["source"] == "user_said"

    def test_facts_are_per_user(self, store):
        store.remember_fact("u1", "target_role", "data analyst")
        assert store.get_facts("u2") == []

    def test_updating_a_fact_replaces_it(self, store):
        store.remember_fact("u1", "target_role", "data analyst")
        store.remember_fact("u1", "target_role", "product manager")
        facts = store.get_facts("u1")
        assert len(facts) == 1
        assert facts[0]["value"] == "product manager"

    def test_keys_are_normalized(self, store):
        store.remember_fact("u1", "Target Role", "designer")
        assert store.get_facts("u1")[0]["key"] == "target_role"

    def test_invalid_source_rejected(self, store):
        with pytest.raises(ValueError, match="Invalid fact source"):
            store.remember_fact("u1", "k", "v", source="guessing")

    def test_web_source_accepted(self, store):
        store.remember_fact("u1", "gate_deadline", "Oct 2026", source="web:https://gate.iitb.ac.in")
        assert store.get_facts("u1")[0]["source"].startswith("web:")

    def test_established_only_filters_inferred(self, store):
        """Inferred facts must never be presented as established truth."""
        store.remember_fact("u1", "said", "I am in final year", source="user_said")
        store.remember_fact("u1", "guessed", "probably wants FAANG", source="inferred")
        established = store.get_facts("u1", established_only=True)
        assert [f["key"] for f in established] == ["said"]

    def test_forget(self, store):
        store.remember_fact("u1", "target_role", "analyst")
        store.forget_fact("u1", "target_role")
        assert store.get_facts("u1") == []


class TestSummaries:
    def test_round_trip_newest_first(self, store):
        store.add_session_summary("u1", "first session")
        time.sleep(0.01)
        store.add_session_summary("u1", "second session")
        summaries = store.get_recent_summaries("u1", limit=2)
        assert summaries[0]["summary"] == "second session"

    def test_limit(self, store):
        for i in range(5):
            store.add_session_summary("u1", f"s{i}")
        assert len(store.get_recent_summaries("u1", limit=3)) == 3


class TestPlans:
    def test_round_trip_with_sources(self, store):
        store.save_plan(
            "u1", "study", "GATE 2027 roadmap",
            {"weeks": [{"n": 1, "focus": "math"}]},
            sources=["https://gate.iitb.ac.in"],
        )
        plans = store.get_plans("u1")
        assert plans[0]["title"] == "GATE 2027 roadmap"
        assert plans[0]["content"]["weeks"][0]["focus"] == "math"
        assert plans[0]["sources"] == ["https://gate.iitb.ac.in"]

    def test_upsert_by_kind_and_title(self, store):
        store.save_plan("u1", "study", "plan", {"v": 1})
        store.save_plan("u1", "study", "plan", {"v": 2})
        plans = store.get_plans("u1", kind="study")
        assert len(plans) == 1
        assert plans[0]["content"]["v"] == 2


class TestSnapshots:
    def test_round_trip(self, store):
        ctx = {"items": [{"type": "message", "role": "user", "content": ["hi"]}]}
        store.save_chat_snapshot("u1", ctx)
        assert store.get_chat_snapshot("u1") == ctx

    def test_missing_returns_none(self, store):
        assert store.get_chat_snapshot("nobody") is None


class TestMemoryContext:
    def test_empty_for_new_user(self, store):
        assert store.build_memory_context("new_user") == ""

    def test_includes_established_facts_and_summaries(self, store):
        store.remember_fact("u1", "target_role", "UPSC aspirant", source="user_said")
        store.remember_fact("u1", "hidden", "guess", source="inferred")
        store.add_session_summary("u1", "Discussed prelims strategy.")
        context = store.build_memory_context("u1")
        assert "UPSC aspirant" in context
        assert "prelims strategy" in context
        assert "guess" not in context, "inferred facts must not appear as truth"
        assert "returning user" in context.lower()
