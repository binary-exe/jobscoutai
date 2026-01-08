"""
Greenhouse ATS API provider.

Public API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
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


class GreenhouseProvider(Provider):
    """Provider for Greenhouse ATS job boards."""

    name = "greenhouse"

    def __init__(self, board_tokens: List[str]):
        """
        Initialize with list of Greenhouse board tokens.
        
        Args:
            board_tokens: List of company board tokens (e.g., ["spotify", "netflix"])
        """
        super().__init__()
        self.board_tokens = board_tokens

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Greenhouse boards."""
        self.reset_stats()

        jobs: List[NormalizedJob] = []

        for token in self.board_tokens[:criteria.max_discovered_ats_tokens]:
            try:
                board_jobs = await self._collect_board(fetcher, token, criteria)
                jobs.extend(board_jobs)
            except Exception as e:
                self.log_error(f"Error collecting from {token}: {e}")

        self.stats.collected = len(jobs)
        return jobs

    async def _collect_board(
        self,
        fetcher: "HttpFetcher",
        token: str,
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from a single Greenhouse board."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            return []

        data = result.json_data
        jobs: List[NormalizedJob] = []

        if not isinstance(data, dict):
            return []

        # Try to get company name from board metadata
        company_name = data.get("name", "") or token

        for j in data.get("jobs", []) or []:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("title", ""))
                if not title:
                    continue

                # Location from nested object
                location_obj = j.get("location", {})
                location = ""
                if isinstance(location_obj, dict):
                    location = normalize_text(location_obj.get("name", ""))
                elif isinstance(location_obj, str):
                    location = normalize_text(location_obj)

                # Remote detection
                remote_type = RemoteType.from_text(location + " " + title)

                # URLs
                job_url = canonicalize_url(j.get("absolute_url", ""))

                # Description
                content = j.get("content", "") or j.get("description", "")
                description = strip_html(content)

                # Posted date
                posted_str = normalize_text(j.get("updated_at", "") or j.get("first_published_at", ""))
                posted_at = parse_date(posted_str)

                # Departments as tags
                departments = j.get("departments", []) or []
                tags = []
                for dept in departments:
                    if isinstance(dept, dict):
                        dept_name = dept.get("name", "")
                        if dept_name:
                            tags.append(normalize_text(dept_name))
                    elif isinstance(dept, str):
                        tags.append(normalize_text(dept))

                # Office locations
                offices = j.get("offices", []) or []
                for office in offices:
                    if isinstance(office, dict):
                        office_loc = office.get("location", "") or office.get("name", "")
                        if office_loc and not location:
                            location = normalize_text(office_loc)

                # Employment type (Greenhouse doesn't always have this)
                employment_types = [EmploymentType.UNKNOWN]

                job = NormalizedJob(
                    provider_id=str(j.get("id", "")),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=normalize_text(company_name),
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    job_url=job_url,
                    apply_url=job_url,
                    description_text=description,
                    tags=tags[:10],
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        return jobs

