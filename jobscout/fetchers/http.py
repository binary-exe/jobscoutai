"""
HTTP fetcher with retries, backoff, throttling, and caching.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import aiohttp


@dataclass
class FetchResult:
    """Result of a fetch operation."""
    url: str
    status: int = 0
    text: str = ""
    json_data: Any = None
    content_type: str = ""
    error: str = ""
    from_cache: bool = False
    elapsed_ms: float = 0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400 and not self.error

    @property
    def is_html(self) -> bool:
        return "text/html" in self.content_type.lower()

    @property
    def is_json(self) -> bool:
        return "json" in self.content_type.lower()


class DomainThrottler:
    """
    Per-domain request throttling to be polite to servers.
    """

    def __init__(self, min_delay_ms: int = 500, max_concurrent_per_domain: int = 2):
        self.min_delay_ms = min_delay_ms
        self.max_concurrent = max_concurrent_per_domain
        self._last_request: Dict[str, float] = {}
        self._domain_sems: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        try:
            return urlsplit(url).netloc.lower()
        except Exception:
            return "unknown"

    async def acquire(self, url: str) -> None:
        """Acquire permission to make a request to this URL's domain."""
        domain = self._get_domain(url)

        async with self._lock:
            if domain not in self._domain_sems:
                self._domain_sems[domain] = asyncio.Semaphore(self.max_concurrent)

        sem = self._domain_sems[domain]
        await sem.acquire()

        # Enforce minimum delay between requests to same domain
        async with self._lock:
            last = self._last_request.get(domain, 0)
            now = time.time()
            elapsed_ms = (now - last) * 1000
            if elapsed_ms < self.min_delay_ms:
                await asyncio.sleep((self.min_delay_ms - elapsed_ms) / 1000)
            self._last_request[domain] = time.time()

    def release(self, url: str) -> None:
        """Release the domain semaphore."""
        domain = self._get_domain(url)
        if domain in self._domain_sems:
            self._domain_sems[domain].release()


class ResponseCache:
    """
    Simple file-based response cache.
    """

    def __init__(self, cache_dir: str, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    def _cache_path(self, url: str) -> str:
        return os.path.join(self.cache_dir, f"{self._cache_key(url)}.json")

    def get(self, url: str) -> Optional[FetchResult]:
        """Get cached response if valid."""
        path = self._cache_path(url)
        if not os.path.exists(path):
            return None

        try:
            # Check TTL
            mtime = os.path.getmtime(path)
            if time.time() - mtime > self.ttl_seconds:
                os.remove(path)
                return None

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return FetchResult(
                url=url,
                status=data.get("status", 200),
                text=data.get("text", ""),
                json_data=data.get("json_data"),
                content_type=data.get("content_type", ""),
                from_cache=True,
            )
        except Exception:
            return None

    def set(self, result: FetchResult) -> None:
        """Cache a successful response."""
        if not result.ok:
            return

        path = self._cache_path(result.url)
        try:
            data = {
                "status": result.status,
                "text": result.text,
                "json_data": result.json_data,
                "content_type": result.content_type,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass


class HttpFetcher:
    """
    Async HTTP fetcher with retries, backoff, throttling, and caching.
    """

    USER_AGENT = "JobScoutBot/2.0 (respectful scraper; contact: admin@example.com)"

    def __init__(
        self,
        timeout_s: int = 20,
        max_retries: int = 3,
        base_delay_ms: int = 1000,
        throttle_delay_ms: int = 500,
        max_concurrent_per_domain: int = 2,
        cache_dir: Optional[str] = None,
        cache_ttl_hours: int = 24,
    ):
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.throttler = DomainThrottler(
            min_delay_ms=throttle_delay_ms,
            max_concurrent_per_domain=max_concurrent_per_domain,
        )
        self.cache = ResponseCache(cache_dir, cache_ttl_hours) if cache_dir else None
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "HttpFetcher":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def start(self) -> None:
        """Initialize the HTTP session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=50,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=headers,
                cookie_jar=aiohttp.CookieJar(),
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def fetch(
        self,
        url: str,
        use_cache: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> FetchResult:
        """
        Fetch a URL with retries and backoff.
        """
        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get(url)
            if cached:
                return cached

        if self._session is None:
            await self.start()

        start_time = time.time()
        last_error = ""
        last_status = 0

        for attempt in range(self.max_retries):
            await self.throttler.acquire(url)
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout_s)
                async with self._session.get(url, timeout=timeout, headers=headers, allow_redirects=True) as resp:
                    last_status = resp.status

                    # Handle rate limiting
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After", "")
                        delay = self._parse_retry_after(retry_after, attempt)
                        last_error = f"Rate limited (429), waiting {delay}ms"
                        await asyncio.sleep(delay / 1000)
                        continue

                    # Handle server errors with retry
                    if resp.status in (500, 502, 503, 504):
                        delay = self._backoff_delay(attempt)
                        last_error = f"Server error ({resp.status}), retrying"
                        await asyncio.sleep(delay / 1000)
                        continue

                    # Client errors - don't retry
                    if resp.status >= 400:
                        return FetchResult(
                            url=url,
                            status=resp.status,
                            error=f"HTTP {resp.status}",
                            elapsed_ms=(time.time() - start_time) * 1000,
                        )

                    # Check content type
                    content_type = resp.headers.get("Content-Type", "")

                    # Skip binary content
                    if any(x in content_type for x in ["image/", "video/", "audio/", "application/octet-stream"]):
                        return FetchResult(
                            url=url,
                            status=resp.status,
                            content_type=content_type,
                            error="Binary content skipped",
                            elapsed_ms=(time.time() - start_time) * 1000,
                        )

                    # Read response
                    text = await resp.text(errors="replace")

                    # Try to parse JSON
                    json_data = None
                    if "json" in content_type.lower():
                        try:
                            json_data = await resp.json(content_type=None)
                        except Exception:
                            try:
                                json_data = json.loads(text)
                            except Exception:
                                pass

                    result = FetchResult(
                        url=url,
                        status=resp.status,
                        text=text,
                        json_data=json_data,
                        content_type=content_type,
                        elapsed_ms=(time.time() - start_time) * 1000,
                    )

                    # Cache successful responses
                    if use_cache and self.cache and result.ok:
                        self.cache.set(result)

                    return result

            except asyncio.TimeoutError:
                last_error = "Timeout"
                delay = self._backoff_delay(attempt)
                await asyncio.sleep(delay / 1000)

            except aiohttp.ClientError as e:
                last_error = str(e)
                delay = self._backoff_delay(attempt)
                await asyncio.sleep(delay / 1000)

            except Exception as e:
                last_error = str(e)
                break

            finally:
                self.throttler.release(url)

        return FetchResult(
            url=url,
            status=last_status,
            error=last_error or "Max retries exceeded",
            elapsed_ms=(time.time() - start_time) * 1000,
        )

    async def fetch_json(self, url: str, use_cache: bool = True) -> FetchResult:
        """Fetch and expect JSON response."""
        result = await self.fetch(
            url,
            use_cache=use_cache,
            headers={"Accept": "application/json"},
        )
        return result

    def _backoff_delay(self, attempt: int) -> int:
        """Calculate exponential backoff delay in milliseconds."""
        return self.base_delay_ms * (2 ** attempt)

    def _parse_retry_after(self, header: str, attempt: int) -> int:
        """Parse Retry-After header or use backoff."""
        if not header:
            return self._backoff_delay(attempt)
        try:
            # Try as seconds
            return int(header) * 1000
        except ValueError:
            pass
        # Default to backoff
        return self._backoff_delay(attempt)

