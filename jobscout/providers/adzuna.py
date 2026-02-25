"""
Adzuna jobs API provider.

Requires JOBSCOUT_ADZUNA_APP_ID and JOBSCOUT_ADZUNA_APP_KEY.
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


ADZUNA_API_ROOT = "https://api.adzuna.com/v1/api/jobs"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class AdzunaProvider(Provider):
    """Provider for Adzuna search API."""

    name = "adzuna"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        app_id = os.environ.get("JOBSCOUT_ADZUNA_APP_ID", "").strip()
        app_key = os.environ.get("JOBSCOUT_ADZUNA_APP_KEY", "").strip()
        if not app_id or not app_key:
            self.log_error("JOBSCOUT_ADZUNA_APP_ID / JOBSCOUT_ADZUNA_APP_KEY not set")
            return []

        country = os.environ.get("JOBSCOUT_ADZUNA_COUNTRY", "gb").strip().lower() or "gb"
        page_size = max(1, min(criteria.max_results_per_source, 50))
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": criteria.primary_query,
            "where": criteria.location or "",
            "results_per_page": page_size,
            "content-type": "application/json",
        }
        request_url = f"{ADZUNA_API_ROOT}/{country}/search/1?{urllib.parse.urlencode(params)}"

        result = await fetcher.fetch_json(request_url, use_cache=True)
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
                    source_url=f"{ADZUNA_API_ROOT}/{country}/search/1",
                    id_paths=[("id",), ("redirect_url",)],
                    title_paths=[("title",)],
                    company_paths=[("company", "display_name"), ("company", "name"), ("company",)],
                    location_paths=[("location", "display_name"), ("location", "area"), ("location",)],
                    description_paths=[("description",)],
                    job_url_paths=[("redirect_url",), ("url",)],
                    apply_url_paths=[("redirect_url",), ("url",)],
                    posted_paths=[("created",)],
                    employment_paths=[("contract_type",), ("contract_time",)],
                    remote_hint_paths=[("title",), ("description",)],
                    salary_min_paths=[("salary_min",)],
                    salary_max_paths=[("salary_max",)],
                    salary_text_paths=[("salary_is_predicted",)],
                    tags_paths=[("category", "label"), ("category",), ("tags",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

