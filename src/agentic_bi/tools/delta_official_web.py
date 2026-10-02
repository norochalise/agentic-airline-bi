"""Trusted live-web search restricted to official Delta and U.S. government sites."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from exa_py import Exa

from agentic_bi.config import exa_api_key

ALLOWED_DOMAINS = ("delta.com", "transportation.gov", "faa.gov", "bts.gov")


def _is_allowed_delta_url(url: str) -> bool:
    """Return True only for an allowed official domain or its subdomains."""

    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return False

    if hostname is None:
        return False

    hostname = hostname.casefold()

    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_DOMAINS
    )


def search_delta_official_web(query: str, num_results: int = 3) -> dict[str, Any]:
    """Search current official airline information using Exa."""

    query = query.strip()

    if not query:
        raise ValueError("Web-search query must not be empty.")

    exa = Exa(api_key=exa_api_key())

    response = exa.search_and_contents(
        query,
        num_results=num_results,
        include_domains=list(ALLOWED_DOMAINS),
        highlights=True,
    )

    results = []

    for result in response.results:
        url = getattr(result, "url", None)

        if not url:
            continue

        if not _is_allowed_delta_url(url):
            continue

        results.append(
            {
                "title": (getattr(result, "title", None) or "Delta"),
                "url": url,
                "highlights": list(getattr(result, "highlights", None) or []),
            }
        )

    return {
        "query": query,
        "source_type": "live_official_web",
        "provider": "exa",
        "result_count": len(results),
        "results": results,
    }
