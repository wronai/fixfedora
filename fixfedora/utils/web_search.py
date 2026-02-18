"""
Zewnętrzne źródła wiedzy – fallback gdy LLM nie zna rozwiązania.
Przeszukuje: Fedora Bugzilla, ask.fedoraproject.org, Reddit, GitHub Issues,
             ALSA/PulseAudio docs, Arch Wiki (Linux-agnostic), SerpAPI.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


def _http_get(url: str, timeout: int = 8) -> Optional[str]:
    """Prosty GET bez zależności zewnętrznych."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "fixfedora/1.0 (Fedora diagnostics tool)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def search_fedora_bugzilla(query: str, max_results: int = 3) -> list[SearchResult]:
    """Szuka w Fedora Bugzilla przez REST API."""
    results = []
    try:
        q = urllib.parse.quote(query)
        url = (
            f"https://bugzilla.redhat.com/rest/bug"
            f"?summary={q}&product=Fedora&status=VERIFIED,CLOSED"
            f"&limit={max_results}&include_fields=id,summary,status,resolution,url"
        )
        data = _http_get(url)
        if not data:
            return []
        bugs = json.loads(data).get("bugs", [])
        for bug in bugs[:max_results]:
            results.append(SearchResult(
                title=f"[BUG #{bug['id']}] {bug['summary']}",
                url=f"https://bugzilla.redhat.com/show_bug.cgi?id={bug['id']}",
                snippet=f"Status: {bug.get('status','?')} | Rozwiązanie: {bug.get('resolution','?')}",
                source="Fedora Bugzilla",
            ))
    except Exception:
        pass
    return results


def search_ask_fedora(query: str, max_results: int = 3) -> list[SearchResult]:
    """Szuka w ask.fedoraproject.org przez Discourse API."""
    results = []
    try:
        q = urllib.parse.quote(query)
        url = f"https://ask.fedoraproject.org/search.json?q={q}&order=latest&page=1"
        data = _http_get(url)
        if not data:
            return []
        topics = json.loads(data).get("topics", [])
        for t in topics[:max_results]:
            results.append(SearchResult(
                title=t.get("title", ""),
                url=f"https://ask.fedoraproject.org/t/{t.get('slug','')}/{t.get('id','')}",
                snippet=f"Odpowiedzi: {t.get('posts_count', 0)} | Widoki: {t.get('views', 0)}",
                source="ask.fedoraproject.org",
            ))
    except Exception:
        pass
    return results


def search_arch_wiki(query: str, max_results: int = 2) -> list[SearchResult]:
    """Arch Wiki – doskonałe źródło dla problemów Linux (nie tylko Arch)."""
    results = []
    try:
        q = urllib.parse.quote(query)
        url = (
            f"https://wiki.archlinux.org/api.php"
            f"?action=opensearch&search={q}&limit={max_results}&format=json"
        )
        data = _http_get(url)
        if not data:
            return []
        parsed = json.loads(data)
        titles = parsed[1] if len(parsed) > 1 else []
        descriptions = parsed[2] if len(parsed) > 2 else []
        urls = parsed[3] if len(parsed) > 3 else []
        for i, title in enumerate(titles[:max_results]):
            results.append(SearchResult(
                title=title,
                url=urls[i] if i < len(urls) else "",
                snippet=descriptions[i] if i < len(descriptions) else "",
                source="Arch Wiki",
            ))
    except Exception:
        pass
    return results


def search_github_issues(query: str, max_results: int = 3) -> list[SearchResult]:
    """GitHub Issues – linuxhardware, ALSA, PipeWire, PulseAudio repos."""
    results = []
    repos = [
        "thesofproject/linux",
        "PipeWire/pipewire",
        "alsa-project/alsa-lib",
    ]
    try:
        q = urllib.parse.quote(f"{query} " + " ".join(f"repo:{r}" for r in repos))
        url = (
            f"https://api.github.com/search/issues"
            f"?q={q}+is:issue&sort=reactions&order=desc&per_page={max_results}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "fixfedora/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("items", [])[:max_results]:
            results.append(SearchResult(
                title=item["title"],
                url=item["html_url"],
                snippet=f"Stan: {item['state']} | 👍 {item.get('reactions',{}).get('+1',0)}",
                source="GitHub Issues",
            ))
    except Exception:
        pass
    return results


def search_serpapi(query: str, api_key: str, max_results: int = 5) -> list[SearchResult]:
    """SerpAPI – Google/Bing search (wymaga klucza API)."""
    results = []
    if not api_key:
        return []
    try:
        q = urllib.parse.quote(f"fedora linux {query} site fix solution")
        url = f"https://serpapi.com/search.json?q={q}&num={max_results}&api_key={api_key}"
        data = _http_get(url)
        if not data:
            return []
        parsed = json.loads(data)
        for r in parsed.get("organic_results", [])[:max_results]:
            results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                source="Google (SerpAPI)",
            ))
    except Exception:
        pass
    return results


def search_ddg(query: str, max_results: int = 5) -> list[SearchResult]:
    """DuckDuckGo Instant Answer API (bez klucza, ograniczone)."""
    results = []
    try:
        q = urllib.parse.quote(f"fedora linux {query}")
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        data = _http_get(url)
        if not data:
            return []
        parsed = json.loads(data)
        # Abstract
        if parsed.get("AbstractText") and parsed.get("AbstractURL"):
            results.append(SearchResult(
                title=parsed.get("Heading", query),
                url=parsed["AbstractURL"],
                snippet=parsed["AbstractText"][:300],
                source="DuckDuckGo",
            ))
        # Related topics
        for topic in parsed.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("FirstURL"):
                results.append(SearchResult(
                    title=topic.get("Text", "")[:80],
                    url=topic["FirstURL"],
                    snippet=topic.get("Text", "")[:200],
                    source="DuckDuckGo",
                ))
    except Exception:
        pass
    return results[:max_results]


def search_all(
    query: str,
    serpapi_key: Optional[str] = None,
    max_per_source: int = 3,
) -> list[SearchResult]:
    """
    Przeszukuje wszystkie dostępne źródła wiedzy.
    Używane jako fallback gdy LLM nie zna rozwiązania.
    """
    all_results: list[SearchResult] = []

    print(f"\n  🔎 Szukam w zewnętrznych źródłach: '{query}'...")

    sources = [
        ("Fedora Bugzilla", lambda: search_fedora_bugzilla(query, max_per_source)),
        ("ask.fedoraproject.org", lambda: search_ask_fedora(query, max_per_source)),
        ("Arch Wiki", lambda: search_arch_wiki(query, max_per_source)),
        ("GitHub Issues", lambda: search_github_issues(query, max_per_source)),
    ]

    if serpapi_key:
        sources.append(("Google (SerpAPI)", lambda: search_serpapi(query, serpapi_key, max_per_source)))
    else:
        sources.append(("DuckDuckGo", lambda: search_ddg(query, max_per_source)))

    for name, fn in sources:
        try:
            results = fn()
            if results:
                print(f"  ✅ {name}: {len(results)} wyników")
                all_results.extend(results)
            else:
                print(f"  ○  {name}: brak wyników")
        except Exception as e:
            print(f"  ❌ {name}: błąd ({e})")

    return all_results


def format_results_for_llm(results: list[SearchResult]) -> str:
    """Formatuje wyniki wyszukiwania do wklejenia w prompt LLM."""
    if not results:
        return "Brak wyników z zewnętrznych źródeł."
    lines = ["=== Wyniki z zewnętrznych źródeł wiedzy ==="]
    for i, r in enumerate(results, 1):
        lines.append(f"\n[{i}] {r.source}: {r.title}")
        lines.append(f"    URL: {r.url}")
        lines.append(f"    {r.snippet}")
    return "\n".join(lines)
