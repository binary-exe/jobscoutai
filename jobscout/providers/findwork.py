"""
Findwork.dev provider.

Requires JOBSCOUT_FINDWORK_API_KEY.
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


FINDWORK_API_URL = "https://findwork.dev/api/jobs/"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class FindworkProvider(Provider):
    """Provider for Findwork API."""

    name = "findwork"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_key = os.environ.get("JOBSCOUT_FINDWORK_API_KEY", "").strip()
        if not api_key:
            self.log_error("JOBSCOUT_FINDWORK_API_KEY not set")
            return []

        params = {"search": criteria.primary_query}
        if criteria.location:
            params["location"] = criteria.location
        request_url = f"{FINDWORK_API_URL}?{urllib.parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Token {api_key}",
        }
        result = await fetcher.fetch(request_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        raw_items = data.get("results")
        if not isinstance(raw_items, list):
            raw_items = data.get("jobs")
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
                    source_url=FINDWORK_API_URL,
                    id_paths=[("id",), ("slug",), ("url",)],
                    title_paths=[("role",), ("title",), ("position",)],
                    company_paths=[("company_name",), ("company",), ("company_name_short",)],
                    location_paths=[("location",), ("location_name",)],
                    description_paths=[("text",), ("description",)],
                    job_url_paths=[("url",), ("job_url",), ("application_url",)],
                    apply_url_paths=[("application_url",), ("url",)],
                    posted_paths=[("date_posted",), ("created_at",), ("published",)],
                    employment_paths=[("employment_type",), ("job_type",), ("type",)],
                    remote_hint_paths=[("remote",), ("location",)],
                    salary_min_paths=[("salary_min",)],
                    salary_max_paths=[("salary_max",)],
                    salary_text_paths=[("salary_text",), ("salary",)],
                    tags_paths=[("keywords",), ("tags",), ("source",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

