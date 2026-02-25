"""
SerpAPI Google Jobs provider.

Uses SerpAPI engine=google_jobs to aggregate jobs from Google Jobs (surfaces Indeed,
LinkedIn, etc.). Opt-in via JOBSCOUT_ENABLED_PROVIDERS. Requires JOBSCOUT_SERPAPI_API_KEY.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlencode, urlparse

from jobscout.models import (
    NormalizedJob,
    Criteria,
    RemoteType,
    EmploymentType,
    normalize_text,
    canonicalize_url,
    now_utc,
)
from jobscout.providers.base import Provider

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher

# Safe source_url (never include api_key).
SOURCE_URL_SAFE = "https://serpapi.com/search?engine=google_jobs"

# Aggregator domains to avoid when picking apply_url (prefer direct/ATS).
_AGGREGATOR_DOMAINS = {
    "indeed.com", "linkedin.com", "glassdoor.com", "ziprecruiter.com",
    "monster.com", "careerbuilder.com", "simplyhired.com", "talent.com",
    "adzuna.com", "jobviewtrack.com", "careerjet.net", "whatjobs.com",
    "juju.com", "reed.co.uk", "jobicy.com", "themuse.com", "bebee.com",
    "dice.com",  # Dice is often direct to company, but we prefer ATS
}
# ATS / company domains we prefer.
_ATS_SIGNALS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workday.com", "myworkdayjobs.com", "jobs.lever.co")


def _domain(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_preferred_apply_link(url: str) -> bool:
    host = _domain(url)
    if not host:
        return False
    if host in _AGGREGATOR_DOMAINS:
        return False
    for sig in _ATS_SIGNALS:
        if sig in host:
            return True
    return True  # Unknown = assume direct


def _pick_apply_url(job_data: dict) -> Optional[str]:
    """Pick best apply URL from apply_options; prefer direct/ATS over aggregators."""
    options = job_data.get("apply_options") or []
    if not options:
        return job_data.get("share_link")
    preferred = None
    fallback = None
    for opt in options:
        link = opt.get("link") if isinstance(opt, dict) else None
        if not link or not link.startswith(("http://", "https://")):
            continue
        if _is_preferred_apply_link(link):
            preferred = link
            break
        if fallback is None:
            fallback = link
    return preferred or fallback or job_data.get("share_link")


def _parse_posted_at(text: str) -> Optional[datetime]:
    """Parse 'X days ago', 'X hours ago', etc."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip().lower()
    m = re.match(r"(\d+)\s*(hour|day|week|month)s?\s*ago", text)
    if not m:
        return None
    try:
        n = int(m.group(1))
        unit = m.group(2)
        now = datetime.now(timezone.utc)
        if unit == "hour":
            return now - timedelta(hours=n)
        if unit == "day":
            return now - timedelta(days=n)
        if unit == "week":
            return now - timedelta(weeks=n)
        if unit == "month":
            return now - timedelta(days=n * 30)
    except (ValueError, TypeError):
        pass
    return None


class SerpAPIGoogleJobsProvider(Provider):
    """Provider for SerpAPI Google Jobs (aggregates Indeed, LinkedIn, etc.)."""

    name = "serpapi_google_jobs"

    def __init__(self, max_pages: Optional[int] = None):
        super().__init__()
        if max_pages is not None:
            self.max_pages = max(1, min(max_pages, 5))
        else:
            try:
                self.max_pages = max(1, min(int(os.environ.get("JOBSCOUT_SERPAPI_MAX_PAGES", "1")), 5))
            except (ValueError, TypeError):
                self.max_pages = 1

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """Collect jobs from SerpAPI Google Jobs."""
        self.reset_stats()
        api_key = os.environ.get("JOBSCOUT_SERPAPI_API_KEY") or os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            self.log_error("JOBSCOUT_SERPAPI_API_KEY not set")
            return []

        query = criteria.primary_query or "remote jobs"
        location = criteria.location or "Remote"
        jobs: List[NormalizedJob] = []
        next_token: Optional[str] = None
        page = 0

        while page < self.max_pages:
            params = {
                "engine": "google_jobs",
                "q": f"{query} {location}",
                "hl": "en",
                "api_key": api_key,
            }
            if next_token:
                params["next_page_token"] = next_token

            url = f"https://serpapi.com/search.json?{urlencode(params)}"
            result = await fetcher.fetch_json(url, use_cache=True)
            if not result.ok:
                self.log_error(f"API request failed: {result.error or result.status}")
                break

            data = result.json_data
            if not isinstance(data, dict):
                self.log_error("Unexpected response format")
                break

            results = data.get("jobs_results") or []
            for j in results:
                if not isinstance(j, dict):
                    continue
                try:
                    job = self._parse_job(j, criteria)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    self.log_error(f"Error parsing job: {e}")

            next_token = None
            pag = data.get("serpapi_pagination") or {}
            if isinstance(pag, dict):
                next_token = pag.get("next_page_token")
            if not next_token:
                break
            page += 1

        self.stats.collected = len(jobs)
        return jobs

    def _parse_job(self, j: dict, criteria: Criteria) -> Optional[NormalizedJob]:
        title = normalize_text(j.get("title", ""))
        company = normalize_text(j.get("company_name", "") or j.get("company", ""))
        if not title or not company:
            return None

        location_raw = normalize_text(j.get("location", "")) or "Remote"
        description = normalize_text(j.get("description", ""))

        # Apply URL: prefer direct/ATS
        apply_url = _pick_apply_url(j)
        apply_url = canonicalize_url(apply_url) if apply_url else ""
        share_link = canonicalize_url(j.get("share_link", ""))
        job_url = apply_url or share_link

        # Remote type from detected_extensions
        ext = j.get("detected_extensions") or {}
        work_from_home = ext.get("work_from_home")
        if work_from_home is True:
            remote_type = RemoteType.REMOTE
        elif "remote" in location_raw.lower() or "anywhere" in location_raw.lower():
            remote_type = RemoteType.REMOTE
        else:
            remote_type = RemoteType.UNKNOWN

        # Employment type
        schedule = (ext.get("schedule_type") or j.get("extensions") or "")
        if isinstance(schedule, list):
            schedule = " ".join(str(s) for s in schedule)
        schedule_str = str(schedule).lower()
        if "contract" in schedule_str or "contractor" in schedule_str:
            employment_types = [EmploymentType.CONTRACT]
        elif "part" in schedule_str:
            employment_types = [EmploymentType.PART_TIME]
        else:
            employment_types = [EmploymentType.from_text(schedule_str) if schedule_str else EmploymentType.UNKNOWN]
        if employment_types == [EmploymentType.UNKNOWN]:
            employment_types = [EmploymentType.FULL_TIME]  # Default for Google Jobs

        # Posted at
        posted_str = ext.get("posted_at") or ""
        if isinstance(j.get("extensions"), list):
            for ex in j["extensions"]:
                if isinstance(ex, str) and "ago" in ex.lower():
                    posted_str = ex
                    break
        posted_at = _parse_posted_at(posted_str)

        provider_id = str(j.get("job_id", ""))
        if not provider_id:
            provider_id = f"{company}:{title}"[:80]

        job = NormalizedJob(
            provider_id=provider_id,
            scraped_at=now_utc(),
            posted_at=posted_at,
            source=self.name,
            source_url=SOURCE_URL_SAFE,
            title=title,
            company=company,
            location_raw=location_raw,
            remote_type=remote_type,
            employment_types=employment_types,
            job_url=job_url,
            apply_url=apply_url or None,
            description_text=description,
            raw_data={k: v for k, v in j.items() if k != "apply_options"},  # Avoid storing full links with tokens
        )
        return job
