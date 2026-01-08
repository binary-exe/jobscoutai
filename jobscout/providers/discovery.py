"""
Discovery utilities for finding ATS tokens and job pages.

Uses DuckDuckGo search to discover:
- Greenhouse board tokens
- Lever site slugs
- Ashby company slugs
- Pages with JobPosting JSON-LD
"""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from jobscout.models import Criteria, normalize_text, canonicalize_url


# Try to import duckduckgo_search
try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    DDGS = None  # type: ignore
    HAS_DDGS = False


# ATS URL patterns
LEVER_SITE_RE = re.compile(
    r"https?://(?:jobs\.(?:eu\.)?lever\.co|[^/]+\.lever\.co)/([A-Za-z0-9\-_]+)(?:/|$)",
    re.IGNORECASE
)
GREENHOUSE_TOKEN_RE = re.compile(
    r"https?://(?:boards\.greenhouse\.io|[^/]+\.greenhouse\.io)/([A-Za-z0-9\-_]+)(?:/|$)",
    re.IGNORECASE
)
ASHBY_SLUG_RE = re.compile(
    r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9\-_]+)(?:/|$)",
    re.IGNORECASE
)
RECRUITEE_RE = re.compile(
    r"https?://([A-Za-z0-9\-_]+)\.recruitee\.com(?:/|$)",
    re.IGNORECASE
)
WORKDAY_RE = re.compile(
    r"https?://([A-Za-z0-9\-_]+)\.wd\d*\.myworkdayjobs\.com(?:/|$)",
    re.IGNORECASE
)


def expand_queries(c: Criteria) -> List[str]:
    """
    Generate search queries from criteria.
    
    Creates variations to maximize discovery of relevant job pages.
    """
    base = normalize_text(c.primary_query)
    loc = c.location or ""

    # Keyword synonyms for automation roles
    synonyms = [
        "workflow automation", "business process automation", "RPA",
        "n8n", "Zapier", "Make.com", "Power Automate",
        "integration engineer", "automation engineer",
        "LLM automation", "AI agent", "AI automation",
        "no-code automation", "iPaaS",
    ]

    queries: List[str] = []
    seen: Set[str] = set()

    def add_query(q: str) -> None:
        q = normalize_text(q)
        if q.lower() not in seen and len(q) > 5:
            queries.append(q)
            seen.add(q.lower())

    # Basic query with location
    add_query(f"{base} {loc} remote job")

    # With must-include keywords
    must = " ".join(c.must_include[:4])
    if must:
        add_query(f"{base} {must} {loc} remote")

    # Synonym variations
    for syn in synonyms[:6]:
        add_query(f'"{syn}" {loc} remote job')
        add_query(f"{syn} {base} remote")

    # ATS-specific queries
    add_query(f"site:jobs.lever.co {base} {loc}")
    add_query(f"site:boards.greenhouse.io {base} {loc}")
    add_query(f"site:jobs.ashbyhq.com {base} {loc}")

    # Career page queries
    add_query(f'site:careers. {base} {loc} remote "JobPosting"')
    add_query(f'inurl:careers {base} {loc} remote')
    add_query(f'inurl:jobs {base} {loc} remote')

    # Contract/freelance specific
    if c.include_contract or c.include_freelance:
        add_query(f"{base} contract {loc} remote")
        add_query(f"{base} freelance {loc} remote")

    return queries


def ddg_search(query: str, max_results: int = 20) -> List[str]:
    """
    Search DuckDuckGo and return URLs.
    
    Returns empty list if duckduckgo_search is not installed.
    """
    if not HAS_DDGS or DDGS is None:
        return []

    urls: List[str] = []

    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            for r in results:
                href = r.get("href") or r.get("link") or r.get("url")
                if href:
                    urls.append(canonicalize_url(href))
    except Exception:
        # DDG can rate limit, timeout, or return no results
        return []

    return urls


def discover_ats_tokens(urls: List[str]) -> dict:
    """
    Extract ATS tokens/slugs from discovered URLs.
    
    Returns dict with keys:
    - lever_sites: List of Lever site slugs
    - greenhouse_tokens: List of Greenhouse board tokens
    - ashby_slugs: List of Ashby company slugs
    - recruitee_companies: List of (company, base_url) tuples
    - other_urls: URLs that might have JobPosting JSON-LD
    """
    lever_sites: Set[str] = set()
    greenhouse_tokens: Set[str] = set()
    ashby_slugs: Set[str] = set()
    recruitee_companies: Set[Tuple[str, str]] = set()
    other_urls: List[str] = []

    for url in urls:
        matched = False

        # Check Lever
        m = LEVER_SITE_RE.search(url)
        if m:
            lever_sites.add(m.group(1))
            matched = True

        # Check Greenhouse
        m = GREENHOUSE_TOKEN_RE.search(url)
        if m:
            greenhouse_tokens.add(m.group(1))
            matched = True

        # Check Ashby
        m = ASHBY_SLUG_RE.search(url)
        if m:
            ashby_slugs.add(m.group(1))
            matched = True

        # Check Recruitee
        m = RECRUITEE_RE.search(url)
        if m:
            company = m.group(1)
            base_url = f"https://{company}.recruitee.com"
            recruitee_companies.add((company, base_url))
            matched = True

        # If not an ATS URL, keep it for schema.org extraction
        if not matched:
            # Skip obvious non-job URLs
            skip_domains = [
                "google.com", "facebook.com", "twitter.com", "linkedin.com/in/",
                "youtube.com", "wikipedia.org", "amazon.com", "reddit.com",
                "github.com/", "stackoverflow.com",
            ]
            if not any(d in url.lower() for d in skip_domains):
                other_urls.append(url)

    return {
        "lever_sites": sorted(lever_sites),
        "greenhouse_tokens": sorted(greenhouse_tokens),
        "ashby_slugs": sorted(ashby_slugs),
        "recruitee_companies": sorted(recruitee_companies),
        "other_urls": other_urls,
    }


def discover_all(criteria: Criteria) -> dict:
    """
    Run full discovery based on criteria.
    
    Returns same dict structure as discover_ats_tokens.
    """
    all_urls: List[str] = []
    seen: Set[str] = set()

    queries = expand_queries(criteria)

    for query in queries:
        results = ddg_search(query, max_results=max(8, criteria.max_search_results // len(queries)))
        for url in results:
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

    # Limit total URLs
    all_urls = all_urls[:criteria.max_search_results]

    return discover_ats_tokens(all_urls)

