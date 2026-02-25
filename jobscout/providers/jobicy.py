"""
Jobicy remote jobs provider.

Public JSON feed at https://jobicy.com/api/v2/remote-jobs. No auth required.
Opt-in via JOBSCOUT_ENABLED_PROVIDERS.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

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

JOBICY_FEED_URL = "https://jobicy.com/api/v2/remote-jobs"


class JobicyProvider(Provider):
    """Provider for Jobicy remote jobs feed."""

    name = "jobicy"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Jobicy API."""
        self.reset_stats()

        result = await fetcher.fetch_json(JOBICY_FEED_URL, use_cache=True)
        if not result.ok or not result.json_data:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data
        jobs_data = data.get("jobs", []) if isinstance(data, dict) else []
        if not isinstance(jobs_data, list):
            self.log_error("Unexpected response format")
            return []

        jobs: List[NormalizedJob] = []
        for j in jobs_data:
            if not isinstance(j, dict):
                continue
            try:
                job = self._parse_job(j)
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

    def _parse_job(self, j: dict) -> Optional[NormalizedJob]:
        title = normalize_text(j.get("jobTitle", "") or j.get("title", ""))
        company = normalize_text(j.get("companyName", "") or j.get("company", ""))
        if not title or not company:
            return None

        job_url = canonicalize_url(j.get("url", ""))
        description = strip_html(j.get("jobDescription", "") or j.get("jobExcerpt", ""))

        job_type = j.get("jobType") or []
        if isinstance(job_type, str):
            job_type = [job_type]
        employment_types = [EmploymentType.from_text(t) for t in job_type if t]
        if not employment_types or all(et == EmploymentType.UNKNOWN for et in employment_types):
            employment_types = [EmploymentType.FULL_TIME]

        location_raw = ""
        job_geo = j.get("jobGeo")
        if job_geo:
            location_raw = str(job_geo) if isinstance(job_geo, str) else ", ".join(str(g) for g in job_geo)

        posted_at = parse_date(str(j.get("pubDate", "")))

        salary_min = j.get("salaryMin")
        salary_max = j.get("salaryMax")
        if salary_min is not None and not isinstance(salary_min, (int, float)):
            try:
                salary_min = float(salary_min)
            except (ValueError, TypeError):
                salary_min = None
        if salary_max is not None and not isinstance(salary_max, (int, float)):
            try:
                salary_max = float(salary_max)
            except (ValueError, TypeError):
                salary_max = None

        tags = []
        industry = j.get("jobIndustry") or []
        if isinstance(industry, list):
            tags = [normalize_text(str(i)) for i in industry[:5] if i]
        elif industry:
            tags = [normalize_text(str(industry))]

        provider_id = str(j.get("id", ""))
        if not provider_id:
            provider_id = f"{company}:{title}"[:80]

        return NormalizedJob(
            provider_id=provider_id,
            scraped_at=now_utc(),
            posted_at=posted_at,
            source=self.name,
            source_url=JOBICY_FEED_URL,
            title=title,
            company=company,
            location_raw=location_raw or "Remote",
            remote_type=RemoteType.REMOTE,
            employment_types=employment_types,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=j.get("salaryCurrency") or "",
            job_url=job_url,
            apply_url=job_url,
            description_text=description,
            tags=tags,
            raw_data=j,
        )
