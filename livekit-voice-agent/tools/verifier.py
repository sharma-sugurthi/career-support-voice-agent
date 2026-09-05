"""Claim verification for high-stakes deliverables.

Before a plan full of numbers and dates is saved, a second LLM pass checks
each checkable claim against the tool evidence actually gathered in this
conversation. Unsupported claims block the save and are named to the model
so it revises or re-researches - fabrication gets caught at the moment it
would become durable.

The verifier fails OPEN on infrastructure errors (a broken verifier must not
take down plan saving) but fails CLOSED on unsupported claims.
"""
import logging
import re

from livekit.agents.llm import LLM, ChatContext

logger = logging.getLogger("career-agent.verifier")

# Numbers with units/currency, years, dates, percentages - the stuff that
# must come from evidence, not memory.
_CHECKABLE = re.compile(
    r"(₹|\$|€|£|\brs\.?\s?\d|\binr\b|\busd\b|\blakh|\bcrore"
    r"|\b\d{4}\b"          # years
    r"|\b\d+(\.\d+)?\s?%"  # percentages
    r"|\b\d[\d,]{3,}\b)",  # big numbers (fees, salaries)
    re.IGNORECASE,
)

ALL_SUPPORTED = "ALL_SUPPORTED"

VERIFIER_INSTRUCTIONS = (
    "You are a strict fact checker. You get EVIDENCE (tool results gathered in "
    "a conversation) and a DRAFT plan. List every specific factual claim in the "
    "DRAFT - amounts, fees, dates, deadlines, named requirements - that the "
    "EVIDENCE does not support. One claim per line, quoted briefly. General "
    "advice, structure, and the user's own stated facts do not need evidence. "
    f"If every checkable claim is supported, reply with exactly: {ALL_SUPPORTED}"
)


def has_checkable_claims(text: str) -> bool:
    return bool(_CHECKABLE.search(text))


def gather_evidence(chat_ctx: ChatContext, max_items: int = 20, max_chars: int = 16000) -> list[str]:
    """Tool outputs from the conversation history - the only ground truth the
    verifier accepts. Most recent items win when trimming."""
    outputs: list[str] = []
    for item in chat_ctx.items:
        if getattr(item, "type", None) == "function_call_output" and not getattr(item, "is_error", False):
            text = str(getattr(item, "output", "") or "")
            if text:
                outputs.append(text)
        elif getattr(item, "type", None) == "message" and getattr(item, "role", "") == "user":
            # what the user themselves said is also legitimate support
            text = item.text_content
            if text:
                outputs.append(f"user said: {text}")
    outputs = outputs[-max_items:]
    total = 0
    kept: list[str] = []
    for text in reversed(outputs):
        total += len(text)
        if total > max_chars:
            break
        kept.append(text)
    return list(reversed(kept))


async def find_unsupported_claims(llm: LLM, draft: str, evidence: list[str]) -> list[str] | None:
    """Returns [] when all claims are supported, a list of unsupported claims
    otherwise, or None when the verifier itself failed (fail open)."""
    ctx = ChatContext.empty()
    ctx.add_message(role="system", content=VERIFIER_INSTRUCTIONS)
    evidence_block = "\n\n".join(evidence) if evidence else "(no tool evidence gathered)"
    ctx.add_message(role="user", content=f"EVIDENCE:\n{evidence_block}\n\nDRAFT:\n{draft}")

    try:
        parts: list[str] = []
        stream = llm.chat(chat_ctx=ctx)
        async with stream:
            async for chunk in stream:
                if chunk.delta and chunk.delta.content:
                    parts.append(chunk.delta.content)
        answer = "".join(parts).strip()
    except Exception as e:
        logger.warning("verifier pass failed, saving without verification: %s", e)
        return None

    if not answer or ALL_SUPPORTED in answer:
        return []
    claims = [line.strip("-• \t") for line in answer.splitlines() if line.strip()]
    return claims[:10]
