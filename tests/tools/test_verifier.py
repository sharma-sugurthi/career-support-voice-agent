"""Offline tests for the claim verifier (no LLM calls)."""
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from livekit.agents.llm import ChatContext  # noqa: E402
from livekit.agents.llm.chat_context import FunctionCall, FunctionCallOutput  # noqa: E402

from tools.verifier import gather_evidence, has_checkable_claims  # noqa: E402


class TestCheckableClaims:
    def test_money_triggers_verification(self):
        assert has_checkable_claims("The fee is ₹1800 for general category")
        assert has_checkable_claims("Tuition is $52,000 per year")
        assert has_checkable_claims("Costs around 25 lakh total")

    def test_years_and_percentages_trigger(self):
        assert has_checkable_claims("Applications close in 2027")
        assert has_checkable_claims("Cutoff was 92.5% last time")

    def test_plain_advice_does_not_trigger(self):
        assert not has_checkable_claims(
            "Week one, revise the basics. Week two, take one mock and review it."
        )


class TestGatherEvidence:
    def _ctx_with_tool_output(self, output: str, is_error: bool = False) -> ChatContext:
        ctx = ChatContext.empty()
        ctx.add_message(role="user", content="what is the GATE fee?")
        ctx.items.append(
            FunctionCall(call_id="c1", name="web_search", arguments="{}")
        )
        ctx.items.append(
            FunctionCallOutput(
                call_id="c1", name="web_search", output=output, is_error=is_error
            )
        )
        return ctx

    def test_tool_outputs_are_evidence(self):
        ctx = self._ctx_with_tool_output("GATE fee is 1800 (source: gate.iitb.ac.in)")
        evidence = gather_evidence(ctx)
        assert any("1800" in e for e in evidence)

    def test_error_outputs_are_not_evidence(self):
        ctx = self._ctx_with_tool_output("timeout", is_error=True)
        evidence = gather_evidence(ctx)
        assert not any("timeout" in e for e in evidence)

    def test_user_statements_are_evidence(self):
        ctx = ChatContext.empty()
        ctx.add_message(role="user", content="my budget is 10 lakh")
        evidence = gather_evidence(ctx)
        assert any("10 lakh" in e for e in evidence)

    def test_assistant_statements_are_not_evidence(self):
        """The model must not be able to cite itself as a source."""
        ctx = ChatContext.empty()
        ctx.add_message(role="assistant", content="the fee is probably 5000")
        assert gather_evidence(ctx) == []

    def test_char_cap_keeps_most_recent(self):
        ctx = ChatContext.empty()
        ctx.add_message(role="user", content="OLD " * 100)
        ctx.add_message(role="user", content="NEWEST_FACT")
        evidence = gather_evidence(ctx, max_chars=50)
        assert any("NEWEST_FACT" in e for e in evidence)
