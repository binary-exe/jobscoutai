"""
Arbeitnow API provider (EU-focused job board).

API docs: https://www.arbeitnow.com/api/job-board-api
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


class ArbeitnowProvider(Provider):
    """Provider for Arbeitnow job board API."""

    name = "arbeitnow"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Arbeitnow API."""
        self.reset_stats()

        url = "https://www.arbeitnow.com/api/job-board-api"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data
        jobs: List[NormalizedJob] = []

        if not isinstance(data, dict):
            self.log_error("Unexpected response format")
            return []

        for j in data.get("data", []) or []:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("title", ""))
                company = normalize_text(j.get("company_name", ""))
                if not title or not company:
                    continue

                location = normalize_text(j.get("location", "")) or "Europe"

                job_url = canonicalize_url(j.get("url", ""))
                description = strip_html(j.get("description", ""))

                # Job type (API sometimes returns list in job_types)
                job_type_val = j.get("job_type", "") or j.get("job_types", "")
                if isinstance(job_type_val, list):
                    job_type_raw = normalize_text(" ".join(str(x) for x in job_type_val if x))
                else:
                    job_type_raw = normalize_text(str(job_type_val or ""))
                employment_types = [EmploymentType.from_text(job_type_raw)]

                # Remote status
                is_remote = j.get("remote", False)
                remote_type = RemoteType.REMOTE if is_remote else RemoteType.from_text(location)

                # Posted date
                created_val = j.get("created_at", "") or j.get("posted_at", "")
                posted_str = normalize_text(str(created_val or ""))
                posted_at = parse_date(posted_str)

                # Tags
                tags_raw = j.get("tags", []) or []
                tags = [normalize_text(str(t)) for t in tags_raw[:10] if t]

                # Company website
                company_website = ""
                company_url = j.get("company_url", "")
                if isinstance(company_url, str):
                    company_website = canonicalize_url(company_url)

                job = NormalizedJob(
                    provider_id=str(j.get("slug", "") or j.get("id", "")),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=company,
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    job_url=job_url,
                    apply_url=job_url,
                    description_text=description,
                    company_website=company_website,
                    tags=tags,
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        self.stats.collected = len(jobs)
        return jobs

