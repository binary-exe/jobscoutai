"""
Remote OK API provider.

API: https://remoteok.io/api
Requires attribution + direct link back.
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


class RemoteOKProvider(Provider):
    """Provider for Remote OK job board API."""

    name = "remoteok"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Remote OK API."""
        self.reset_stats()

        url = "https://remoteok.io/api"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data
        jobs: List[NormalizedJob] = []

        if not isinstance(data, list):
            self.log_error("Unexpected response format")
            return []

        # First item is usually metadata, skip it
        for j in data[1:]:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("position", ""))
                company = normalize_text(j.get("company", ""))
                if not title or not company:
                    continue

                location = normalize_text(j.get("location", "")) or "Remote"

                job_url = canonicalize_url(j.get("url", ""))
                apply_url = canonicalize_url(j.get("apply_url", "")) or job_url

                description = strip_html(j.get("description", ""))

                # Tags
                tags_raw = j.get("tags", []) or []
                tags = [normalize_text(str(t)) for t in tags_raw[:10] if t]

                # Employment type from tags
                employment_types = [EmploymentType.UNKNOWN]
                tags_lower = " ".join(tags).lower()
                if "contract" in tags_lower:
                    employment_types = [EmploymentType.CONTRACT]
                elif "full" in tags_lower:
                    employment_types = [EmploymentType.FULL_TIME]

                # Posted date
                posted_str = str(j.get("date", ""))
                posted_at = parse_date(posted_str)

                # Epoch timestamp
                if not posted_at and j.get("epoch"):
                    posted_at = parse_date(str(j.get("epoch")))

                # Remote OK is remote-only
                remote_type = RemoteType.REMOTE

                # Salary
                salary_str = j.get("salary", "")
                salary_min = None
                salary_max = None
                if salary_str:
                    # Parse salary ranges like "$100,000 - $150,000"
                    import re
                    matches = re.findall(r"\$?([\d,]+)", str(salary_str))
                    if matches:
                        try:
                            salary_min = float(matches[0].replace(",", ""))
                            if len(matches) > 1:
                                salary_max = float(matches[1].replace(",", ""))
                        except ValueError:
                            pass

                # Company info
                company_logo = j.get("company_logo", "") or j.get("logo", "")

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
                    apply_url=apply_url,
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

