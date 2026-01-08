"""
Ashby ATS API provider.

Ashby has a public job board API similar to Greenhouse/Lever.
API: https://jobs.ashbyhq.com/api/non-user-graphql
"""

from __future__ import annotations

import json
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


class AshbyProvider(Provider):
    """Provider for Ashby ATS job boards."""

    name = "ashby"

    def __init__(self, company_slugs: List[str]):
        """
        Initialize with list of Ashby company slugs.
        
        Args:
            company_slugs: List of company slugs (e.g., ["notion", "linear"])
        """
        super().__init__()
        self.company_slugs = company_slugs

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Ashby boards."""
        self.reset_stats()

        jobs: List[NormalizedJob] = []

        for slug in self.company_slugs[:criteria.max_discovered_ats_tokens]:
            try:
                company_jobs = await self._collect_company(fetcher, slug, criteria)
                jobs.extend(company_jobs)
            except Exception as e:
                self.log_error(f"Error collecting from {slug}: {e}")

        self.stats.collected = len(jobs)
        return jobs

    async def _collect_company(
        self,
        fetcher: "HttpFetcher",
        slug: str,
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from a single Ashby company."""
        # Ashby uses a GraphQL-like API
        url = f"https://jobs.ashbyhq.com/{slug}"
        api_url = "https://jobs.ashbyhq.com/api/non-user-graphql"

        # GraphQL query for job postings
        query = """
        query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) {
            jobBoard: jobBoardWithTeams(
                organizationHostedJobsPageName: $organizationHostedJobsPageName
            ) {
                teams {
                    id
                    name
                    jobs {
                        id
                        title
                        employmentType
                        locationName
                        isRemote
                        descriptionHtml
                        publishedDate
                    }
                }
            }
        }
        """

        payload = {
            "operationName": "ApiJobBoardWithTeams",
            "variables": {"organizationHostedJobsPageName": slug},
            "query": query,
        }

        result = await fetcher.fetch(
            api_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        # Try POST request manually (since our fetcher is GET-only, fallback to simple GET)
        # For now, try the direct job listing page
        result = await fetcher.fetch(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")

        if not result.ok:
            return []

        try:
            data = json.loads(result.text) if result.text else None
        except json.JSONDecodeError:
            return []

        if not isinstance(data, dict):
            return []

        jobs: List[NormalizedJob] = []

        # Parse jobs from API response
        job_list = data.get("jobs", []) or []

        for j in job_list:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("title", ""))
                if not title:
                    continue

                location = normalize_text(j.get("locationName", "") or j.get("location", ""))

                is_remote = j.get("isRemote", False)
                remote_type = RemoteType.REMOTE if is_remote else RemoteType.from_text(location)

                # Job URL
                job_id = j.get("id", "")
                job_url = f"https://jobs.ashbyhq.com/{slug}/{job_id}" if job_id else url

                # Description
                desc_html = j.get("descriptionHtml", "") or j.get("description", "")
                description = strip_html(desc_html)

                # Employment type
                emp_type = j.get("employmentType", "")
                employment_types = [EmploymentType.from_text(emp_type)]

                # Posted date
                published = j.get("publishedDate", "") or j.get("updatedAt", "")
                posted_at = parse_date(published)

                # Team/department
                team = normalize_text(j.get("teamName", "") or j.get("team", ""))
                tags = [team] if team else []

                job = NormalizedJob(
                    provider_id=str(job_id),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=normalize_text(slug),
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    job_url=canonicalize_url(job_url),
                    apply_url=canonicalize_url(job_url),
                    description_text=description,
                    tags=tags,
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        return jobs

