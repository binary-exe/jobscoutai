"""
DevITjobs UK provider.

Public XML feed at https://devitjobs.uk/job_feed.xml. No auth required.
Opt-in via JOBSCOUT_ENABLED_PROVIDERS.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional, TYPE_CHECKING

from jobscout.models import (
    NormalizedJob,
    Criteria,
    RemoteType,
    EmploymentType,
    normalize_text,
    canonicalize_url,
    now_utc,
)
from jobscout.extract.html import strip_html
from jobscout.providers.base import Provider

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher

DEVITJOBS_FEED_URL = "https://devitjobs.uk/job_feed.xml"


def _elem_text(parent: Optional[ET.Element], tag: str, default: str = "") -> str:
    if parent is None:
        return default
    child = parent.find(tag)
    if child is None:
        return default
    return (child.text or "").strip()


class DevITjobsUKProvider(Provider):
    """Provider for DevITjobs UK XML job feed."""

    name = "devitjobs_uk"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from DevITjobs UK XML feed."""
        self.reset_stats()

        result = await fetcher.fetch(DEVITJOBS_FEED_URL, use_cache=True)
        if not result.ok:
            self.log_error(f"Feed request failed: {result.error or result.status}")
            return []

        text = result.text if hasattr(result, "text") else ""
        if not text:
            self.log_error("Empty response")
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            self.log_error(f"XML parse error: {e}")
            return []

        jobs: List[NormalizedJob] = []
        for job_elem in root.findall(".//job"):
            try:
                job = self._parse_job(job_elem)
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

    def _parse_job(self, elem: ET.Element) -> Optional[NormalizedJob]:
        title = normalize_text(_elem_text(elem, "title"))
        company = normalize_text(_elem_text(elem, "company"))
        if not title or not company:
            return None

        location_raw = normalize_text(_elem_text(elem, "location")) or "UK"
        description = strip_html(_elem_text(elem, "description"))
        salary_str = _elem_text(elem, "salary")

        job_url = canonicalize_url(_elem_text(elem, "url") or _elem_text(elem, "link"))
        if not job_url:
            job_url = f"https://devitjobs.uk/jobs?q={title.replace(' ', '+')}"[:500]

        salary_min = None
        salary_max = None
        if salary_str:
            import re
            matches = re.findall(r"[\d,]+", str(salary_str))
            if matches:
                try:
                    salary_min = float(matches[0].replace(",", ""))
                    if len(matches) > 1:
                        salary_max = float(matches[1].replace(",", ""))
                except ValueError:
                    pass

        provider_id = _elem_text(elem, "id") or _elem_text(elem, "guid")
        if not provider_id:
            provider_id = f"{company}:{title}"[:80]

        return NormalizedJob(
            provider_id=provider_id,
            scraped_at=now_utc(),
            posted_at=None,
            source=self.name,
            source_url=DEVITJOBS_FEED_URL,
            title=title,
            company=company,
            location_raw=location_raw,
            remote_type=RemoteType.UNKNOWN,
            employment_types=[EmploymentType.UNKNOWN],
            salary_min=salary_min,
            salary_max=salary_max,
            job_url=job_url,
            apply_url=job_url,
            description_text=description,
            raw_data={},
        )
