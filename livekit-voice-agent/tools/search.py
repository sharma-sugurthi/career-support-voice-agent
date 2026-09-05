"""Web search with a keyless default.

Default backend is DuckDuckGo via the `ddgs` library - no API key, no signup,
works for anyone who cloned the repo. Optional upgrades via env:

    SEARCH_PROVIDER=tavily   + TAVILY_API_KEY   (better quality for LLMs)
    SEARCH_PROVIDER=brave    + BRAVE_API_KEY

Every result carries its URL - the citation contract the prompts rely on.
"""
import asyncio
import os

import httpx

DEFAULT_PROVIDER = "ddgs"
SUPPORTED_PROVIDERS = ("ddgs", "tavily", "brave")


def resolve_search_provider() -> str:
    provider = os.environ.get("SEARCH_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown SEARCH_PROVIDER '{provider}'. Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    return provider


def _normalize(title: str, url: str, snippet: str) -> dict:
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "snippet": (snippet or "").strip()[:500],
    }


def _ddgs_search_sync(query: str, max_results: int) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        raw = list(ddgs.text(query, max_results=max_results))
    return [_normalize(r.get("title", ""), r.get("href", ""), r.get("body", "")) for r in raw]


async def _tavily_search(query: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": query,
                "max_results": max_results,
            },
        )
        resp.raise_for_status()
        raw = resp.json().get("results", [])
    return [_normalize(r.get("title", ""), r.get("url", ""), r.get("content", "")) for r in raw]


async def _brave_search(query: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": os.environ["BRAVE_API_KEY"]},
        )
        resp.raise_for_status()
        raw = resp.json().get("web", {}).get("results", [])
    return [
        _normalize(r.get("title", ""), r.get("url", ""), r.get("description", "")) for r in raw
    ]


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web. Returns [{title, url, snippet}]; empty list on no results.
    Raises on network/config errors - callers turn that into a spoken 'could
    not search' rather than a guess."""
    provider = resolve_search_provider()
    if provider == "tavily":
        return await _tavily_search(query, max_results)
    if provider == "brave":
        return await _brave_search(query, max_results)
    # ddgs is a sync library - keep the event loop free
    return await asyncio.to_thread(_ddgs_search_sync, query, max_results)
