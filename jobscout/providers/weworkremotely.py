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
                title_tag = item.find("title")
                link_tag = item.find("link")
                guid_tag = item.find("guid")
                raw_title = normalize_text(title_tag.get_text() if title_tag else "")
                link = canonicalize_url(link_tag.get_text() if link_tag else "")
                guid = normalize_text(guid_tag.get_text() if guid_tag else "")

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
                desc_tag = item.find("description")
                desc_html = desc_tag.get_text() if desc_tag else ""
                description = strip_html(desc_html)

                # Category/region
                category_tag = item.find("category")
                category = normalize_text(category_tag.get_text() if category_tag else "")
                # Some feeds have multiple categories
                if not category:
                    categories = item.find_all("category") or []
                    if categories:
                        category = normalize_text(categories[0].get_text() or "")

                region_tag = item.find("region")
                region = normalize_text(region_tag.get_text() if region_tag else "")

                # Posted date
                pub_tag = item.find("pubDate")
                pub_date = normalize_text(pub_tag.get_text() if pub_tag else "")
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
                    # Stable ID for dedupe across runs (prefer guid; fallback to canonical link)
                    provider_id=(guid or link),
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

