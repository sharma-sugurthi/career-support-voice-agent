"""Fetch a web page and extract its readable text.

Respects robots.txt, caps download size and content length, and always
returns the source URL and retrieval time - the citation contract.
"""
import asyncio
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urlsplit, urlunsplit

import httpx
import trafilatura

USER_AGENT = "career-support-voice-agent/1.0 (+https://github.com/sharma-sugurthi/career-support-voice-agent)"
MAX_DOWNLOAD_BYTES = 2_000_000
MAX_CONTENT_CHARS = 8_000
TIMEOUT = 15


def robots_url_for(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))


def is_allowed(robots_txt: str, url: str, user_agent: str = USER_AGENT) -> bool:
    parser = robotparser.RobotFileParser()
    parser.parse(robots_txt.splitlines())
    return parser.can_fetch(user_agent, url)


def extract_readable(html: str) -> str:
    """Article text from HTML; falls back to nothing rather than tag soup."""
    text = trafilatura.extract(html) or ""
    return text.strip()


async def fetch_url(url: str) -> dict:
    """Fetch one page. Returns {content, url, retrieved_at}.
    Raises PermissionError when robots.txt disallows the fetch, and httpx
    errors on network failure - callers speak the failure, never guess."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Only http(s) URLs can be fetched, got: {url}")

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers, follow_redirects=True) as client:
        # robots.txt first; unreachable/missing robots means allowed by convention
        try:
            robots_resp = await client.get(robots_url_for(url))
            if robots_resp.status_code == 200 and not is_allowed(robots_resp.text, url):
                raise PermissionError(f"robots.txt disallows fetching {url}")
        except httpx.HTTPError:
            pass

        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text[:MAX_DOWNLOAD_BYTES]

    content = await asyncio.to_thread(extract_readable, html)
    if not content:
        content = " ".join(html.split())[:MAX_CONTENT_CHARS]

    return {
        "content": content[:MAX_CONTENT_CHARS],
        "url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
