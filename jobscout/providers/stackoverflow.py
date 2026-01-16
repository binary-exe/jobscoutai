"""
Stack Overflow Jobs RSS provider.

RSS feed: https://stackoverflow.com/jobs/feed
"""

from __future__ import annotations

import urllib.parse
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


class StackOverflowProvider(Provider):
    """Provider for Stack Overflow Jobs RSS feed."""

    name = "stackoverflow"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Stack Overflow Jobs RSS."""
        self.reset_stats()

        # Stack Overflow Jobs RSS supports query parameters
        query = urllib.parse.quote(criteria.primary_query)
        url = f"https://stackoverflow.com/jobs/feed?q={query}&r=true"  # r=true for remote

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

                # Category/tags
                category_tags = item.find_all("category")
                categories = [normalize_text(cat.get_text()) for cat in category_tags if cat]
                tags = categories[:10]

                # Location
                location_tag = item.find("location")
                location = normalize_text(location_tag.get_text() if location_tag else "Remote")

                # Posted date
                pub_tag = item.find("pubDate")
                pub_date = normalize_text(pub_tag.get_text() if pub_tag else "")
                posted_at = parse_date(pub_date)

                # Extract company from title (format: "Job Title at Company")
                company = "Unknown"
                title = raw_title
                if " at " in raw_title.lower():
                    parts = raw_title.rsplit(" at ", 1)
                    title = normalize_text(parts[0])
                    company = normalize_text(parts[1]) if len(parts) > 1 else "Unknown"

                # Employment type from tags
                employment_types = [EmploymentType.UNKNOWN]
                tags_lower = " ".join(tags).lower()
                if "contract" in tags_lower:
                    employment_types = [EmploymentType.CONTRACT]
                elif "full" in tags_lower or "full-time" in tags_lower:
                    employment_types = [EmploymentType.FULL_TIME]
                elif "part" in tags_lower:
                    employment_types = [EmploymentType.PART_TIME]

                # Remote type - Stack Overflow has remote jobs
                remote_type = RemoteType.REMOTE if "remote" in location.lower() else RemoteType.from_text(location)

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
