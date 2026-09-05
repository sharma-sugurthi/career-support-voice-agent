"""function_tool wrappers the agents actually call.

Failures return a plain "could not do X" string instead of raising, so the
model says what went wrong rather than guessing an answer - and successful
retrieval results always carry their sources.
"""
import logging

from livekit.agents import RunContext, function_tool

from .fetch import fetch_url
from .finance import compute_budget, convert_currency
from .search import search_web

logger = logging.getLogger("career-agent.tools")


@function_tool()
async def web_search(context: RunContext, query: str) -> dict | str:
    """Search the web for current information: fees, exam dates, deadlines,
    company hiring processes, salaries, rankings. Use this INSTEAD of
    recalling any fact that has a number or date attached. Tell the user the
    source name when you use a result.

    Args:
        query: what to search for, phrased like a search query
    """
    try:
        results = await search_web(query, max_results=5)
    except Exception as e:
        logger.warning("web_search failed: %s", e)
        return "Search failed - tell the user you could not look this up right now. Do not guess."
    if not results:
        return "No results found - tell the user you could not find this. Do not guess."
    return {
        "results": results,
        "reminder": "Name the source out loud when you state facts from these results.",
    }


@function_tool()
async def read_webpage(context: RunContext, url: str) -> dict | str:
    """Read the text of one specific web page, for example an official exam
    notification, a university fees page, or a company careers page. Use a
    URL from web_search results or one the user gave you.

    Args:
        url: the full http(s) address of the page to read
    """
    try:
        return await fetch_url(url)
    except PermissionError:
        return "That site does not allow automated reading - tell the user and suggest they open it themselves."
    except Exception as e:
        logger.warning("read_webpage failed for %s: %s", url, e)
        return "Could not read that page - tell the user, and do not invent its contents."


@function_tool()
async def currency_convert(
    context: RunContext, amount: float, from_currency: str, to_currency: str
) -> dict | str:
    """Convert money between currencies at the latest official exchange rate.
    ALWAYS use this for currency conversion - never do the math yourself.

    Args:
        amount: the amount to convert
        from_currency: 3-letter code like USD, EUR, INR
        to_currency: 3-letter code like USD, EUR, INR
    """
    try:
        return await convert_currency(amount, from_currency, to_currency)
    except Exception as e:
        logger.warning("currency_convert failed: %s", e)
        return "Could not get the exchange rate - tell the user, and do not estimate one."


@function_tool()
async def budget_total(context: RunContext, items: list[dict]) -> dict | str:
    """Add up budget line items exactly. ALWAYS use this to total costs -
    never add numbers in your head.

    Args:
        items: list of {"label": name of the cost, "amount": number} entries
    """
    try:
        return compute_budget(items)
    except Exception as e:
        return f"Budget items were malformed ({e}) - fix the items and call again."


@function_tool()
async def save_plan(
    context: RunContext, kind: str, title: str, plan_text: str, sources: list[str] | None = None
) -> str:
    """Save a plan you built with the user - a study schedule, a prep roadmap,
    a budget - so future sessions can continue it. Include the source URLs for
    any facts in the plan.

    Args:
        kind: one of study, prep, budget, schedule, other
        title: short name for the plan, e.g. "GATE 2027 roadmap"
        plan_text: the full plan content
        sources: URLs backing the facts used in this plan
    """
    from .verifier import find_unsupported_claims, gather_evidence, has_checkable_claims

    userdata = context.userdata

    # Verification gate: a plan with money/dates in it only becomes durable
    # if this conversation's tool evidence supports those claims.
    if has_checkable_claims(plan_text):
        evidence = gather_evidence(context.session.history)
        unsupported = await find_unsupported_claims(context.session.llm, plan_text, evidence)
        if unsupported:  # [] = all supported, None = verifier down (fail open)
            listed = "; ".join(unsupported)
            return (
                "NOT saved. These claims have no supporting tool result in this "
                f"conversation: {listed}. Look each one up with your tools or "
                "remove it, then save again."
            )

    userdata.store.save_plan(userdata.user_id, kind, title, plan_text, sources or [])
    return f"Saved plan '{title}'."


@function_tool()
async def get_plans(context: RunContext, kind: str | None = None) -> dict | str:
    """Recall plans saved for this user in earlier sessions.

    Args:
        kind: optionally filter to one of study, prep, budget, schedule, other
    """
    userdata = context.userdata
    plans = userdata.store.get_plans(userdata.user_id, kind=kind)
    if not plans:
        return "No saved plans yet."
    return {"plans": plans}
