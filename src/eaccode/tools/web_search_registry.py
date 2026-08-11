"""Web search registry (G.6) — pluggable search providers, no API keys.

Providers are plain callables ``(query, limit) -> list[SearchResult]``.
The default provider scrapes DuckDuckGo's HTML endpoint (keyless,
bounded); a custom provider can be registered at runtime, which is how
an API-keyed backend (SerpAPI, Tavily, ...) would plug in later.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import httpx

SearchProvider = Callable[["str", int], "list[SearchResult]"]


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


_providers: dict[str, SearchProvider] = {}


def register_provider(name: str, fn: SearchProvider) -> None:
    _providers[name] = fn


def available_providers() -> list[str]:
    return sorted(_providers)


def get_provider(name: str) -> SearchProvider:
    if name not in _providers:
        raise KeyError(
            f"unknown search provider {name!r}; available: "
            f"{', '.join(available_providers())}"
        )
    return _providers[name]


def search(query: str, limit: int = 5, provider: str = "ddg") -> list[SearchResult]:
    """Search with the named provider; empty list on failure (never raises)."""
    try:
        fn = get_provider(provider)
        return fn(query, min(max(limit, 1), 10)) or []
    except Exception:
        return []


def _ssl_verify() -> bool:
    """J.9: settings.ssl_verify (default True) for outbound HTTP."""
    try:
        from eaccode.config.paths import EaccodePaths
        from eaccode.config.settings import Settings

        return Settings.load(EaccodePaths().settings_file).ssl_verify
    except Exception:
        return True


def _ddg_provider(query: str, limit: int) -> list[SearchResult]:
    import html as html_mod

    resp = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        timeout=15,
        verify=_ssl_verify(),  # J.9
        follow_redirects=True,
        headers={"User-Agent": "eaccode/0.1 (+https://github.com/Kurt-03/eac-code)"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"search failed: HTTP {resp.status_code}")
    results: list[SearchResult] = []
    # Parse the classic <a class="result__a"> + <a class="result__snippet"> rows.
    for block in re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?(?:<a[^>]*class="result__snippet"[^>]*>(.*?)</a>)?',
        resp.text,
        re.DOTALL,
    ):
        url, title_html, snippet_html = block
        if not url.startswith("http"):
            continue
        results.append(
            SearchResult(
                title=html_mod.unescape(re.sub(r"<[^>]+>", "", title_html)).strip(),
                url=url,
                snippet=html_mod.unescape(
                    re.sub(r"<[^>]+>", "", snippet_html or "")
                ).strip(),
            )
        )
        if len(results) >= limit:
            break
    return results


register_provider("ddg", _ddg_provider)
