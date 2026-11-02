"""Small DuckDuckGo HTML search helper used to ground chat answers."""

from __future__ import annotations

import re
from html import unescape
from typing import Any, Dict, List

import requests

_DDGO_HTML = "https://duckduckgo.com/html/"
_USER_AGENT = "LectureFlow/1.0 (study assistant)"


def search_web(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Return a small list of web result snippets. Never raises."""
    query = (query or "").strip()
    if not query:
        return []
    try:
        response = requests.get(
            _DDGO_HTML,
            params={"q": query},
            headers={"User-Agent": _USER_AGENT},
            timeout=8,
        )
        response.raise_for_status()
        html = response.text
    except Exception:
        return []

    result_links = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    result_snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    results: List[Dict[str, Any]] = []
    for index, (href, title_html) in enumerate(result_links[:limit]):
        snippet_html = result_snippets[index] if index < len(result_snippets) else ""
        title = unescape(re.sub(r"<[^>]+>", "", title_html)).strip()
        snippet = unescape(re.sub(r"<[^>]+>", "", snippet_html)).strip()
        if not (title or snippet):
            continue
        results.append({"title": title, "snippet": snippet, "url": href})
    return results
