"""
USAJobs API provider.

Docs: https://developer.usajobs.gov/
Requires JOBSCOUT_USAJOBS_API_KEY and JOBSCOUT_USAJOBS_USER_AGENT.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from typing import List, TYPE_CHECKING

from jobscout.models import Criteria, NormalizedJob
from jobscout.providers.base import Provider
from jobscout.providers._provider_utils import build_job

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


USAJOBS_API_URL = "https://data.usajobs.gov/api/search"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class USAJobsProvider(Provider):
    """Provider for USAJobs API."""

    name = "usajobs"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_key = os.environ.get("JOBSCOUT_USAJOBS_API_KEY", "").strip()
        user_agent = os.environ.get("JOBSCOUT_USAJOBS_USER_AGENT", "").strip()
        if not api_key or not user_agent:
            self.log_error("JOBSCOUT_USAJOBS_API_KEY / JOBSCOUT_USAJOBS_USER_AGENT not set")
            return []

        params = {
            "Keyword": criteria.primary_query,
            "LocationName": criteria.location or "",
            "ResultsPerPage": max(1, min(criteria.max_results_per_source, 100)),
        }
        request_url = f"{USAJOBS_API_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "Host": "data.usajobs.gov",
            "Authorization-Key": api_key,
            "User-Agent": user_agent,
        }
        result = await fetcher.fetch(request_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        search_result = data.get("SearchResult")
        if not isinstance(search_result, dict):
            self.log_error("Unexpected response format")
            return []
        raw_items = search_result.get("SearchResultItems")
        if not isinstance(raw_items, list):
            self.log_error("Unexpected SearchResultItems format")
            return []

        jobs: List[NormalizedJob] = []
        for wrapper in raw_items[: criteria.max_results_per_source]:
            if not isinstance(wrapper, dict):
                continue
            item = wrapper.get("MatchedObjectDescriptor")
            if not isinstance(item, dict):
                continue
            try:
                job = build_job(
                    item=item,
                    criteria=criteria,
                    source_name=self.name,
                    source_url=USAJOBS_API_URL,
                    id_paths=[("PositionID",), ("PositionURI",)],
                    title_paths=[("PositionTitle",)],
                    company_paths=[("OrganizationName",), ("DepartmentName",)],
                    location_paths=[("PositionLocationDisplay",), ("PositionLocation",)],
                    description_paths=[("UserArea", "Details", "JobSummary"), ("QualificationSummary",)],
                    job_url_paths=[("PositionURI",)],
                    apply_url_paths=[("ApplyURI", 0), ("PositionURI",)],
                    posted_paths=[("PublicationStartDate",), ("PositionStartDate",)],
                    employment_paths=[("PositionSchedule",), ("PositionOfferingType",)],
                    remote_hint_paths=[("PositionLocationDisplay",)],
                    salary_min_paths=[("PositionRemuneration", 0, "MinimumRange")],
                    salary_max_paths=[("PositionRemuneration", 0, "MaximumRange")],
                    salary_text_paths=[("PositionRemuneration", 0, "Description")],
                    tags_paths=[("JobCategory",), ("PositionSchedule",), ("SubAgencyName",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

