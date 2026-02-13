"""
Working Nomads provider (low-bot-risk JSON endpoint).

Working Nomads does not reliably serve an RSS feed anymore. They expose a small
public JSON feed we can consume without aggressive scraping:

- https://www.workingnomads.com/api/exposed_jobs/
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

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


class WorkingNomadsProvider(Provider):
    """Provider for Working Nomads public JSON feed."""

    name = "workingnomads"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Working Nomads JSON feed."""
        self.reset_stats()

        url = "https://www.workingnomads.com/api/exposed_jobs/"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data
        if not isinstance(data, list):
            self.log_error("Unexpected response format")
            return []

        jobs: List[NormalizedJob] = []

        for j in data[:criteria.max_results_per_source]:
            if not isinstance(j, dict):
                continue
            try:
                title = normalize_text(j.get("title", ""))
                company = normalize_text(j.get("company_name", "")) or "Unknown"
                if not title:
                    continue

                job_url = canonicalize_url(j.get("url", ""))
                if not job_url:
                    continue

                description = strip_html(j.get("description", ""))
                location = normalize_text(j.get("location", "")) or "Remote"
                posted_at = parse_date(normalize_text(j.get("pub_date", "")))

                tags_raw = j.get("tags", []) or []
                tags = [normalize_text(str(t)) for t in tags_raw[:10] if t]

                # Employment type is not explicit; best-effort from tags/category
                employment_types = [EmploymentType.UNKNOWN]
                cat = normalize_text(j.get("category_name", ""))
                if cat:
                    et = EmploymentType.from_text(cat)
                    if et != EmploymentType.UNKNOWN:
                        employment_types = [et]

                job = NormalizedJob(
                    # Stable ID for dedupe across runs
                    provider_id=job_url,
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=company,
                    location_raw=location,
                    remote_type=RemoteType.REMOTE,
                    employment_types=employment_types,
                    job_url=job_url,
                    apply_url=job_url,
                    description_text=description,
                    tags=tags,
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        self.stats.collected = len(jobs)
        return jobs
