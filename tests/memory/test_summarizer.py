"""Tests for the session summarizer's transcript building (no LLM calls)."""
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parent.parent.parent / "livekit-voice-agent"
sys.path.insert(0, str(AGENT_DIR))

from livekit.agents.llm import ChatContext  # noqa: E402

from memory.summarizer import transcript_from_chat_ctx  # noqa: E402


def _ctx(*turns: tuple[str, str]) -> ChatContext:
    ctx = ChatContext.empty()
    for role, text in turns:
        ctx.add_message(role=role, content=text)
    return ctx


class TestTranscript:
    def test_includes_user_and_assistant_turns(self):
        ctx = _ctx(("user", "I want to switch to marketing"), ("assistant", "Great goal."))
        transcript = transcript_from_chat_ctx(ctx)
        assert "user: I want to switch to marketing" in transcript
        assert "assistant: Great goal." in transcript

    def test_excludes_system_messages(self):
        ctx = _ctx(("system", "secret instructions"), ("user", "hello"))
        transcript = transcript_from_chat_ctx(ctx)
        assert "secret instructions" not in transcript

    def test_truncates_keeping_the_tail(self):
        ctx = _ctx(("user", "early " * 500), ("user", "THE_LATEST_TURN"))
        transcript = transcript_from_chat_ctx(ctx, max_chars=100)
        assert len(transcript) <= 100
        assert "THE_LATEST_TURN" in transcript

    def test_empty_context(self):
        assert transcript_from_chat_ctx(ChatContext.empty()) == ""
