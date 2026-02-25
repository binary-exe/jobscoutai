"""
Reed API provider.

Docs: https://www.reed.co.uk/developers
Requires JOBSCOUT_REED_API_KEY.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
from typing import List, TYPE_CHECKING

from jobscout.models import Criteria, NormalizedJob
from jobscout.providers.base import Provider
from jobscout.providers._provider_utils import build_job

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


REED_API_URL = "https://www.reed.co.uk/api/1.0/search"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class ReedProvider(Provider):
    """Provider for Reed API."""

    name = "reed"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_key = os.environ.get("JOBSCOUT_REED_API_KEY", "").strip()
        if not api_key:
            self.log_error("JOBSCOUT_REED_API_KEY not set")
            return []

        basic_token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {basic_token}",
        }
        params = {
            "keywords": criteria.primary_query,
            "locationName": criteria.location or "",
            "resultsToTake": max(1, min(criteria.max_results_per_source, 100)),
            "resultsToSkip": 0,
        }
        request_url = f"{REED_API_URL}?{urllib.parse.urlencode(params)}"

        result = await fetcher.fetch(request_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        raw_items = data.get("results")
        if not isinstance(raw_items, list):
            self.log_error("Unexpected response format")
            return []

        jobs: List[NormalizedJob] = []
        for item in raw_items[: criteria.max_results_per_source]:
            if not isinstance(item, dict):
                continue
            try:
                job = build_job(
                    item=item,
                    criteria=criteria,
                    source_name=self.name,
                    source_url=REED_API_URL,
                    id_paths=[("jobId",), ("jobUrl",)],
                    title_paths=[("jobTitle",), ("title",)],
                    company_paths=[("employerName",), ("companyName",), ("company",)],
                    location_paths=[("locationName",), ("location",)],
                    description_paths=[("jobDescription",), ("description",)],
                    job_url_paths=[("jobUrl",), ("url",)],
                    apply_url_paths=[("jobUrl",), ("url",)],
                    posted_paths=[("date",)],
                    employment_paths=[("contractType",), ("fullTime",)],
                    remote_hint_paths=[("locationName",)],
                    salary_min_paths=[("minimumSalary",)],
                    salary_max_paths=[("maximumSalary",)],
                    salary_text_paths=[("salary",), ("salaryText",)],
                    tags_paths=[("jobTitle",), ("applications",)],
                    company_site_paths=[("employerProfileId",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

