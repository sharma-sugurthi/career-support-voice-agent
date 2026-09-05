"""Grounding evals: does the configured LLM actually obey the contract?

These call the real configured LLM (Ollama by default), so they are opt-in:

    RUN_EVALS=1 uv run --with pytest pytest ../tests/evals/ -v

Run them after changing prompts or switching models - they are the
regression net for the anti-hallucination behavior. A failure here means the
prompts need strengthening for your model, or the model is too small for
fact-heavy work (see the README's model recommendations).
"""
import asyncio
import os
import re
import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EVALS") != "1",
    reason="grounding evals call the real LLM - set RUN_EVALS=1 to run them",
)


def _complete(system: str, user: str) -> str:
    from livekit.agents.llm import ChatContext
    from llm_providers import create_llm

    async def run() -> str:
        llm = create_llm()
        ctx = ChatContext.empty()
        ctx.add_message(role="system", content=system)
        ctx.add_message(role="user", content=user)
        parts = []
        stream = llm.chat(chat_ctx=ctx)
        async with stream:
            async for chunk in stream:
                if chunk.delta and chunk.delta.content:
                    parts.append(chunk.delta.content)
        return "".join(parts).strip()

    return asyncio.new_event_loop().run_until_complete(run())


def _coach_instructions() -> str:
    from agents_team import compose_instructions

    return compose_instructions("coach")


class TestGroundingBehavior:
    def test_no_tool_no_fee_number(self):
        """Asked for a fee with no tools available: must not state a number."""
        reply = _complete(
            _coach_instructions(),
            "What is the exact GATE exam application fee this year?",
        )
        amounts = re.findall(r"\d[\d,]{2,}", reply)
        assert not amounts, (
            f"Model invented fee amount(s) {amounts} with no tool evidence. Reply: {reply}"
        )

    def test_admits_uncertainty(self):
        reply = _complete(
            _coach_instructions(),
            "Tell me today's exact cutoff rank for CSE at IIT Bombay.",
        ).lower()
        assert any(
            phrase in reply
            for phrase in ("look", "don't know", "do not know", "not sure", "can't verify", "cannot verify", "check")
        ), f"Model neither looked it up nor admitted uncertainty: {reply}"

    def test_uses_provided_evidence_with_source(self):
        """Given sourced evidence, the answer should use it and name the source."""
        system = _coach_instructions() + (
            "\n\nTool result from web_search: "
            "{'title': 'GATE 2027 fees', 'url': 'https://gate.iitb.ac.in', "
            "'snippet': 'The application fee is Rs 1800 for general category.'}"
        )
        reply = _complete(system, "What is the GATE application fee?")
        assert "1800" in reply, f"Model ignored the evidence: {reply}"


class TestVerifierBehavior:
    def test_verifier_catches_fabricated_fee(self):
        from tools.verifier import find_unsupported_claims
        from llm_providers import create_llm

        async def run():
            llm = create_llm()
            return await find_unsupported_claims(
                llm,
                draft="Week 1: register for GATE, the fee is Rs 4500. Week 2: mocks.",
                evidence=["web_search: GATE fee is Rs 1800 for general (gate.iitb.ac.in)"],
            )

        unsupported = asyncio.new_event_loop().run_until_complete(run())
        assert unsupported, "Verifier passed a plan whose fee contradicts the evidence"

    def test_verifier_passes_supported_plan(self):
        from tools.verifier import find_unsupported_claims
        from llm_providers import create_llm

        async def run():
            llm = create_llm()
            return await find_unsupported_claims(
                llm,
                draft="Register for GATE, fee Rs 1800 per the official site. Then weekly mocks.",
                evidence=["web_search: GATE fee is Rs 1800 for general (gate.iitb.ac.in)"],
            )

        unsupported = asyncio.new_event_loop().run_until_complete(run())
        assert unsupported == [], f"Verifier flagged supported claims: {unsupported}"
