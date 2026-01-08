"""
Lever ATS API provider.

Public API: https://api.lever.co/v0/postings/{site}?mode=json
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


class LeverProvider(Provider):
    """Provider for Lever ATS job postings."""

    name = "lever"

    def __init__(self, sites: List[str]):
        """
        Initialize with list of Lever site slugs.
        
        Args:
            sites: List of company site slugs (e.g., ["stripe", "figma"])
        """
        super().__init__()
        self.sites = sites

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from Lever sites."""
        self.reset_stats()

        jobs: List[NormalizedJob] = []

        for site in self.sites[:criteria.max_discovered_ats_tokens]:
            try:
                site_jobs = await self._collect_site(fetcher, site, criteria)
                jobs.extend(site_jobs)
            except Exception as e:
                self.log_error(f"Error collecting from {site}: {e}")

        self.stats.collected = len(jobs)
        return jobs

    async def _collect_site(
        self,
        fetcher: "HttpFetcher",
        site: str,
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from a single Lever site."""
        url = f"https://api.lever.co/v0/postings/{site}?mode=json"

        result = await fetcher.fetch_json(url)
        if not result.ok or not result.json_data:
            return []

        data = result.json_data
        jobs: List[NormalizedJob] = []

        if not isinstance(data, list):
            return []

        for j in data:
            if not isinstance(j, dict):
                continue

            try:
                title = normalize_text(j.get("text", "") or j.get("title", ""))
                if not title:
                    continue

                # Categories (location, team, commitment)
                categories = j.get("categories", {}) or {}
                location = ""
                team = ""
                commitment = ""

                if isinstance(categories, dict):
                    location = normalize_text(categories.get("location", ""))
                    team = normalize_text(categories.get("team", ""))
                    commitment = normalize_text(categories.get("commitment", ""))

                # Remote detection
                remote_type = RemoteType.from_text(location + " " + title)

                # URLs
                job_url = canonicalize_url(
                    j.get("hostedUrl", "")
                    or j.get("applyUrl", "")
                    or j.get("url", "")
                )
                apply_url = canonicalize_url(j.get("applyUrl", "")) or job_url

                # Description
                desc_plain = j.get("descriptionPlain", "")
                desc_html = j.get("description", "")
                description = normalize_text(desc_plain) if desc_plain else strip_html(desc_html)

                # Additional lists content
                lists = j.get("lists", []) or []
                for lst in lists:
                    if isinstance(lst, dict):
                        list_content = lst.get("content", "")
                        if list_content:
                            description += "\n\n" + strip_html(list_content)

                # Posted date (createdAt is Unix timestamp in ms)
                created_at = j.get("createdAt")
                posted_at = None
                if created_at:
                    posted_at = parse_date(str(created_at))

                # Employment type from commitment
                employment_types = [EmploymentType.from_text(commitment)]

                # Tags
                tags = []
                if team:
                    tags.append(team)
                if commitment:
                    tags.append(commitment)

                # Workplace type
                workplace_type = j.get("workplaceType", "")
                if workplace_type:
                    if "remote" in workplace_type.lower():
                        remote_type = RemoteType.REMOTE
                    elif "hybrid" in workplace_type.lower():
                        remote_type = RemoteType.HYBRID

                job = NormalizedJob(
                    provider_id=str(j.get("id", "")),
                    scraped_at=now_utc(),
                    posted_at=posted_at,
                    source=self.name,
                    source_url=url,
                    title=title,
                    company=normalize_text(site),  # Use site as company name
                    location_raw=location,
                    remote_type=remote_type,
                    employment_types=employment_types,
                    job_url=job_url,
                    apply_url=apply_url,
                    description_text=description[:8000],
                    tags=tags[:10],
                    raw_data=j,
                )
                jobs.append(job)

            except Exception as e:
                self.log_error(f"Error parsing job: {e}")
                continue

        return jobs

