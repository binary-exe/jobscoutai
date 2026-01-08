"""
Recruitee/Teamtailor/Personio-style ATS provider.

These ATS systems often have public JSON APIs at:
- https://{company}.recruitee.com/api/offers
- https://careers.{company}.com/api/offers (Teamtailor)
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

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


class RecruiteeProvider(Provider):
    """Provider for Recruitee-style ATS job boards."""

    name = "recruitee"

    def __init__(self, companies: List[Tuple[str, str]]):
        """
        Initialize with list of (company_name, api_base_url) tuples.
        
        Args:
            companies: List of tuples like [("acme", "https://acme.recruitee.com")]
        """
        super().__init__()
        self.companies = companies

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Recruitee-style boards."""
        self.reset_stats()

        jobs: List[NormalizedJob] = []

        for company_name, base_url in self.companies[:criteria.max_discovered_ats_tokens]:
            try:
                company_jobs = await self._collect_company(
                    fetcher, company_name, base_url, criteria
                )
                jobs.extend(company_jobs)
            except Exception as e:
                self.log_error(f"Error collecting from {company_name}: {e}")

        self.stats.collected = len(jobs)
        return jobs

    async def _collect_company(
        self,
        fetcher: "HttpFetcher",
        company_name: str,
        base_url: str,
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from a single Recruitee-style board."""
        # Try common API endpoints
        api_paths = [
            "/api/offers",
            "/api/offers/",
            "/api/v1/offers",
            "/api/job-postings",
        ]

        data = None
        used_url = ""

        for path in api_paths:
            url = base_url.rstrip("/") + path
            result = await fetcher.fetch_json(url)
            if result.ok and result.json_data:
                data = result.json_data
                used_url = url
                break

        if not data:
            return []

        jobs: List[NormalizedJob] = []

        # Handle different response formats
        offers = []
        if isinstance(data, dict):
            offers = data.get("offers", []) or data.get("jobs", []) or data.get("data", [])
        elif isinstance(data, list):
            offers = data

        for j in offers:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(
                    j.get("title", "")
                    or j.get("name", "")
                    or j.get("position", "")
                )
                if not title:
                    continue

                # Location
                location = normalize_text(j.get("location", "") or j.get("city", ""))
                country = normalize_text(j.get("country", ""))
                if country and country not in location:
                    location = f"{location}, {country}" if location else country

                # Remote detection
                is_remote = j.get("remote", False) or j.get("isRemote", False)
                remote_type = RemoteType.REMOTE if is_remote else RemoteType.from_text(location)

                # URLs
                careers_url = j.get("careers_url", "") or j.get("url", "") or j.get("careerSiteUrl", "")
                job_url = canonicalize_url(careers_url)
                if not job_url and j.get("slug"):
                    job_url = f"{base_url.rstrip('/')}/o/{j['slug']}"

                apply_url = canonicalize_url(j.get("apply_url", "")) or job_url

                # Description
                desc = j.get("description", "") or j.get("descriptionHtml", "")
                description = strip_html(desc)

                # Employment type
                emp_type = normalize_text(j.get("employment_type", "") or j.get("employmentType", ""))
                employment_types = [EmploymentType.from_text(emp_type)]

                # Posted date
                posted_str = (
                    j.get("published_at", "")
                    or j.get("publishedAt", "")
                    or j.get("created_at", "")
                )
                posted_at = parse_date(posted_str)

                # Department/category
                department = normalize_text(j.get("department", "") or j.get("category", ""))
                tags = [department] if department else []

                # Experience level
                experience = normalize_text(j.get("experience", "") or j.get("min_experience", ""))
                if experience:
                    tags.append(experience)

                job = NormalizedJob(
                    provider_id=str(j.get("id", "") or j.get("slug", "")),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=used_url,
                    title=title,
                    company=normalize_text(company_name),
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    job_url=job_url,
                    apply_url=apply_url,
                    description_text=description,
                    tags=tags[:10],
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        return jobs

