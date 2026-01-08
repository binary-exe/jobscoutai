"""
We Work Remotely RSS provider.

RSS feed: https://weworkremotely.com/remote-jobs.rss
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


class WWRRssProvider(Provider):
    """Provider for We Work Remotely RSS feed."""

    name = "weworkremotely"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from We Work Remotely RSS."""
        self.reset_stats()

        url = "https://weworkremotely.com/remote-jobs.rss"

        result = await fetcher.fetch(url)
        if not result.ok:
            self.log_error(f"RSS request failed: {result.error or result.status}")
            return []

        jobs: List[NormalizedJob] = []

        try:
            soup = BeautifulSoup(result.text, "xml")
            items = soup.find_all("item")
        except Exception as e:
            self.log_error(f"XML parsing failed: {e}")
            return []

        for item in items[:criteria.max_results_per_source]:
            try:
                # Title format is often "Company - Job Title"
                raw_title = normalize_text(item.findtext("title") or "")
                link = canonicalize_url(item.findtext("link") or "")

                if not raw_title or not link:
                    continue

                # Parse company from title
                company = ""
                title = raw_title
                if " - " in raw_title:
                    parts = raw_title.split(" - ", 1)
                    company = normalize_text(parts[0])
                    title = normalize_text(parts[1])
                elif ": " in raw_title:
                    parts = raw_title.split(": ", 1)
                    company = normalize_text(parts[0])
                    title = normalize_text(parts[1])

                if not company:
                    company = "Unknown"

                # Description
                desc_html = item.findtext("description") or ""
                description = strip_html(desc_html)

                # Category/region
                category = normalize_text(item.findtext("category") or "")
                region = normalize_text(item.findtext("region") or "")

                # Posted date
                pub_date = normalize_text(item.findtext("pubDate") or "")
                posted_at = parse_date(pub_date)

                # Extract type from category
                employment_types = [EmploymentType.UNKNOWN]
                if category:
                    et = EmploymentType.from_text(category)
                    if et != EmploymentType.UNKNOWN:
                        employment_types = [et]

                # WWR is remote-only
                remote_type = RemoteType.REMOTE
                location = region or "Remote"

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

        self.stats.collected = len(jobs)
        return jobs

