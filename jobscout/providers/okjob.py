"""
OkJob provider.

API shape varies by partner integration, so this adapter supports a configurable
endpoint via JOBSCOUT_OKJOB_API_URL and optional JOBSCOUT_OKJOB_API_KEY.
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


DEFAULT_OKJOB_API_URL = "https://okjob.io/api/jobs"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class OkJobProvider(Provider):
    """Provider for OkJob API-like endpoints."""

    name = "okjob"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_url = os.environ.get("JOBSCOUT_OKJOB_API_URL", DEFAULT_OKJOB_API_URL).strip() or DEFAULT_OKJOB_API_URL
        api_key = os.environ.get("JOBSCOUT_OKJOB_API_KEY", "").strip()

        params = {
            "q": criteria.primary_query,
            "location": criteria.location or "",
            "limit": max(1, min(criteria.max_results_per_source, 100)),
            "page": 1,
        }
        request_url = f"{api_url}?{urllib.parse.urlencode(params)}"

        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            headers["X-API-Key"] = api_key

        result = await fetcher.fetch(request_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        raw_items = data.get("jobs")
        if not isinstance(raw_items, list):
            raw_items = data.get("results")
        if not isinstance(raw_items, list):
            raw_items = data.get("data")
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
                    id_paths=[("id",), ("slug",), ("url",)],
                    title_paths=[("title",), ("position",), ("name",)],
                    company_paths=[("company", "name"), ("company_name",), ("company",)],
                    location_paths=[("location",), ("location_name",), ("city",)],
                    description_paths=[("description",), ("summary",), ("snippet",)],
                    job_url_paths=[("url",), ("job_url",), ("link",)],
                    apply_url_paths=[("apply_url",), ("application_url",), ("url",)],
                    posted_paths=[("posted_at",), ("created_at",), ("published_at",)],
                    employment_paths=[("employment_type",), ("type",), ("job_type",)],
                    remote_hint_paths=[("remote",), ("is_remote",), ("location",)],
                    salary_min_paths=[("salary_min",)],
                    salary_max_paths=[("salary_max",)],
                    salary_text_paths=[("salary",), ("salary_text",)],
                    tags_paths=[("tags",), ("skills",), ("categories",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

