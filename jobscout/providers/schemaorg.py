"""
Schema.org JobPosting provider.

Extracts jobs from pages using schema.org JSON-LD markup.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from jobscout.models import NormalizedJob, Criteria
from jobscout.extract.jsonld import extract_job_postings_from_html
from jobscout.providers.base import Provider

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher
    from jobscout.fetchers.browser import BrowserFetcher


class SchemaOrgProvider(Provider):
    """Provider that extracts JobPosting JSON-LD from arbitrary pages."""

    name = "schema_org"

    def __init__(self, urls: List[str], use_browser: bool = False):
        """
        Initialize with list of URLs to check for JobPosting JSON-LD.
        
        Args:
            urls: List of page URLs to scrape
            use_browser: If True, use browser fetcher for JS-rendered pages
        """
        super().__init__()
        self.urls = urls
        self.use_browser = use_browser
        self._browser_fetcher: "BrowserFetcher | None" = None

    def set_browser_fetcher(self, fetcher: "BrowserFetcher") -> None:
        """Set the browser fetcher for JS-rendered pages."""
        self._browser_fetcher = fetcher

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from URLs by extracting JobPosting JSON-LD."""
        self.reset_stats()

        jobs: List[NormalizedJob] = []
        seen_ids: set = set()

        for url in self.urls[:criteria.max_search_results]:
            try:
                page_jobs = await self._collect_page(fetcher, url, criteria)
                for job in page_jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        jobs.append(job)
            except Exception as e:
                self.log_error(f"Error collecting from {url}: {e}")

        self.stats.collected = len(jobs)
        return jobs

    async def _collect_page(
        self,
        fetcher: "HttpFetcher",
        url: str,
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Extract jobs from a single page."""
        html = ""

        # Try browser first if enabled and available
        if self.use_browser and self._browser_fetcher:
            result = await self._browser_fetcher.fetch(url)
            if result.ok:
                html = result.text

        # Fall back to HTTP fetcher
        if not html:
            result = await fetcher.fetch(url)
            if not result.ok:
                return []
            html = result.text

        if not html:
            return []

        # Extract JobPosting JSON-LD
        jobs = extract_job_postings_from_html(html, source_url=url)

        # Update source to indicate discovery method
        for job in jobs:
            job.source = self.name
            job.source_url = url

        return jobs

