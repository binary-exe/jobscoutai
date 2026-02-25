"""
Jobs2Careers provider.

Historical docs are HTTP-only and integration-specific. This adapter supports a
configurable endpoint and optional API key.
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


DEFAULT_J2C_API_URL = "http://api.jobs2careers.com/api/jobsearch"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class Jobs2CareersProvider(Provider):
    """Provider for Jobs2Careers partner API."""

    name = "jobs2careers"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_url = os.environ.get("JOBSCOUT_JOBS2CAREERS_API_URL", DEFAULT_J2C_API_URL).strip() or DEFAULT_J2C_API_URL
        api_key = os.environ.get("JOBSCOUT_JOBS2CAREERS_API_KEY", "").strip()

        params = {
            "q": criteria.primary_query,
            "l": criteria.location or "",
            "page": 1,
            "pagesize": max(1, min(criteria.max_results_per_source, 100)),
            "format": "json",
        }
        if api_key:
            params["api_key"] = api_key
        request_url = f"{api_url}?{urllib.parse.urlencode(params)}"

        result = await fetcher.fetch(request_url, use_cache=True, headers={"Accept": "application/json"})
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        raw_items = data.get("jobs")
        if not isinstance(raw_items, list):
            raw_items = data.get("results")
        if not isinstance(raw_items, list):
            response = data.get("response")
            raw_items = response.get("jobs") if isinstance(response, dict) else None
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
                    source_url=api_url,
                    id_paths=[("id",), ("job_id",), ("url",)],
                    title_paths=[("title",), ("job_title",)],
                    company_paths=[("company",), ("company_name",)],
                    location_paths=[("location",), ("city",), ("state",)],
                    description_paths=[("description",), ("snippet",)],
                    job_url_paths=[("url",), ("job_url",)],
                    apply_url_paths=[("apply_url",), ("url",)],
                    posted_paths=[("date",), ("posted_at",)],
                    employment_paths=[("employment_type",), ("type",)],
                    remote_hint_paths=[("remote",), ("location",)],
                    salary_min_paths=[("salary_min",)],
                    salary_max_paths=[("salary_max",)],
                    salary_text_paths=[("salary",)],
                    tags_paths=[("category",), ("categories",), ("skills",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

