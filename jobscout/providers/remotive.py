"""
Remotive API provider.

API docs: https://remotive.com/api/remote-jobs
Requires attribution + link back; has rate limiting guidance.
"""

from __future__ import annotations

import urllib.parse
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


class RemotiveProvider(Provider):
    """Provider for Remotive job board API."""

    name = "remotive"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Remotive API."""
        self.reset_stats()

        # Remotive supports `search`. `limit` is inconsistently supported, so we omit it for reliability.
        q = urllib.parse.quote(criteria.primary_query)
        url = f"https://remotive.com/api/remote-jobs?search={q}"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data
        jobs: List[NormalizedJob] = []

        if not isinstance(data, dict) or "jobs" not in data:
            self.log_error("Unexpected response format")
            return []

        for j in data.get("jobs", []):
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("title", ""))
                company = normalize_text(j.get("company_name", ""))
                if not title or not company:
                    continue

                location = normalize_text(
                    j.get("candidate_required_location", "")
                    or j.get("location", "")
                )

                job_url = canonicalize_url(j.get("url", ""))
                description = strip_html(j.get("description", ""))

                job_type_raw = normalize_text(j.get("job_type", ""))
                employment_types = [EmploymentType.from_text(job_type_raw)]

                posted_str = normalize_text(j.get("publication_date", ""))
                posted_at = parse_date(posted_str)

                # Extract category/tags
                category = normalize_text(j.get("category", ""))
                tags = [category] if category else []

                # Remotive is remote-only
                remote_type = RemoteType.REMOTE

                # Salary (if available)
                salary_str = j.get("salary", "")
                salary_min = None
                salary_max = None

                job = NormalizedJob(
                    provider_id=str(j.get("id", "")),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=company,
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    salary_min=salary_min,
                    salary_max=salary_max,
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

