"""
Fetcher layer for JobScout.

Provides HTTP and browser-based fetching with:
- Retries with exponential backoff
- Per-domain rate limiting
- Response caching
- 429/503 handling with Retry-After
"""

from jobscout.fetchers.http import HttpFetcher, FetchResult
from jobscout.fetchers.browser import BrowserFetcher

__all__ = ["HttpFetcher", "BrowserFetcher", "FetchResult"]

