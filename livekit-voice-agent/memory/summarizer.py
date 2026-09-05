"""End-of-session summarization: one LLM call that turns the conversation
into a short memory the next session starts from."""
import logging

from livekit.agents.llm import LLM, ChatContext

logger = logging.getLogger("career-agent.memory")

SUMMARY_INSTRUCTIONS = (
    "You write memory notes for a career coaching assistant. Summarize the "
    "conversation below in 2-4 plain sentences: the user's situation and goals, "
    "what was discussed or decided, and what the obvious next step is. "
    "Only include things actually said in the conversation - never add or guess "
    "details. If the conversation contains nothing career-related, reply with "
    "exactly: NOTHING_TO_REMEMBER"
)


def transcript_from_chat_ctx(chat_ctx: ChatContext, max_chars: int = 12000) -> str:
    """Flatten user/assistant turns into a plain transcript."""
    lines: list[str] = []
    for item in chat_ctx.items:
        if getattr(item, "type", None) != "message":
            continue
        if item.role not in ("user", "assistant"):
            continue
        text = item.text_content
        if text:
            lines.append(f"{item.role}: {text}")
    transcript = "\n".join(lines)
    # keep the tail - the latest turns matter most for "where we left off"
    return transcript[-max_chars:]


async def summarize_session(llm: LLM, chat_ctx: ChatContext) -> str | None:
    """Return a short summary of the session, or None if there is nothing
    worth remembering (or the LLM call fails - memory must never crash close)."""
    transcript = transcript_from_chat_ctx(chat_ctx)
    if len(transcript.strip()) < 40:
        return None

    ctx = ChatContext.empty()
    ctx.add_message(role="system", content=SUMMARY_INSTRUCTIONS)
    ctx.add_message(role="user", content=transcript)

    try:
        parts: list[str] = []
        stream = llm.chat(chat_ctx=ctx)
        async with stream:
            async for chunk in stream:
                if chunk.delta and chunk.delta.content:
                    parts.append(chunk.delta.content)
        summary = "".join(parts).strip()
    except Exception as e:
        logger.warning("session summary failed (memory skipped this time): %s", e)
        return None

    if not summary or "NOTHING_TO_REMEMBER" in summary:
        return None
    return summary
