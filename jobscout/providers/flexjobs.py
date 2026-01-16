"""
FlexJobs provider.

Note: FlexJobs is a paid job board and may not have a public API.
This provider attempts to use RSS if available, otherwise returns empty.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from bs4 import BeautifulSoup

from jobscout.models import (
    NormalizedJob,
    Criteria,
    RemoteType,
    EmploymentType,
    normalize_text,
    canonicalize_url,
    parse_date,
    now_utc,
)
from jobscout.extract.html import strip_html
from jobscout.providers.base import Provider

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


class FlexJobsProvider(Provider):
    """Provider for FlexJobs (limited access - paid board)."""

    name = "flexjobs"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """
        Collect jobs from FlexJobs.
        
        Note: FlexJobs is a paid job board and typically requires authentication.
        This implementation attempts to access public RSS if available.
        """
        self.reset_stats()

        # FlexJobs may have RSS feeds for specific categories
        # Try common RSS endpoints
        urls_to_try = [
            "https://www.flexjobs.com/jobs.rss",
            "https://www.flexjobs.com/remote-jobs.rss",
        ]

        jobs: List[NormalizedJob] = []

        for url in urls_to_try:
            result = await fetcher.fetch(url)
            if result.ok:
                try:
                    soup = BeautifulSoup(result.text, "xml")
                    items = soup.find_all("item")
                    
                    for item in items[:criteria.max_results_per_source]:
                        try:
                            title_tag = item.find("title")
                            link_tag = item.find("link")
                            raw_title = normalize_text(title_tag.get_text() if title_tag else "")
                            link = canonicalize_url(link_tag.get_text() if link_tag else "")

                            if not raw_title or not link:
                                continue

                            # Description
                            desc_tag = item.find("description")
                            desc_html = desc_tag.get_text() if desc_tag else ""
                            description = strip_html(desc_html)

                            # Category
                            category_tag = item.find("category")
                            category = normalize_text(category_tag.get_text() if category_tag else "")

                            # Posted date
                            pub_tag = item.find("pubDate")
                            pub_date = normalize_text(pub_tag.get_text() if pub_tag else "")
                            posted_at = parse_date(pub_date)

                            # Extract company from title
                            company = "Unknown"
                            title = raw_title
                            if " - " in raw_title:
                                parts = raw_title.split(" - ", 1)
                                company = normalize_text(parts[0])
                                title = normalize_text(parts[1])

                            # Employment type
                            employment_types = [EmploymentType.UNKNOWN]
                            if category:
                                et = EmploymentType.from_text(category)
                                if et != EmploymentType.UNKNOWN:
                                    employment_types = [et]

                            # FlexJobs is remote-focused
                            remote_type = RemoteType.REMOTE
                            location = "Remote"

                            tags = [category] if category else []

                            job = NormalizedJob(
                                scraped_at=now_utc(),
                                posted_at=posted_at,
                                source=self.name,
                                source_url=url,
                                title=title,
                                company=company,
                                location_raw=location,
                                remote_type=remote_type,
                                employment_types=employment_types,
                                job_url=link,
                                apply_url=link,
                                description_text=description,
                                tags=tags,
                            )
                            jobs.append(job)

                        except Exception as e:
                            self.log_error(f"Error parsing item: {e}")
                            continue
                    
                    # If we got results from this URL, break
                    if jobs:
                        break
                        
                except Exception as e:
                    self.log_error(f"XML parsing failed for {url}: {e}")
                    continue

        # If no RSS available, log and return empty
        if not jobs:
            self.log_error("No accessible RSS feed found for FlexJobs (may require authentication)")

        self.stats.collected = len(jobs)
        return jobs
