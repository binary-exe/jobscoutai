"""
Juju provider.

Juju publisher feeds are commonly HTTP-only and partner-specific. This adapter
uses configurable endpoint + optional API key.
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


DEFAULT_JUJU_API_URL = "http://www.juju.com/publisher/jobs/"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class JujuProvider(Provider):
    """Provider for Juju publisher APIs/feeds."""

    name = "juju"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_url = os.environ.get("JOBSCOUT_JUJU_API_URL", DEFAULT_JUJU_API_URL).strip() or DEFAULT_JUJU_API_URL
        api_key = os.environ.get("JOBSCOUT_JUJU_API_KEY", "").strip()
        if not api_key:
            self.log_error("JOBSCOUT_JUJU_API_KEY not set")
            return []

        params = {
            "q": criteria.primary_query,
            "l": criteria.location or "",
            "page": 1,
            "count": max(1, min(criteria.max_results_per_source, 100)),
            "api_key": api_key,
        }
        request_url = f"{api_url}?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json"}
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
                    id_paths=[("id",), ("job_id",), ("url",)],
                    title_paths=[("title",), ("job_title",)],
                    company_paths=[("company",), ("company_name",)],
                    location_paths=[("location",), ("city",), ("region",)],
                    description_paths=[("description",), ("snippet",)],
                    job_url_paths=[("url",), ("job_url",)],
                    apply_url_paths=[("apply_url",), ("url",)],
                    posted_paths=[("posted_at",), ("date",)],
                    employment_paths=[("employment_type",), ("type",)],
                    remote_hint_paths=[("remote",), ("location",)],
                    salary_min_paths=[("salary_min",)],
                    salary_max_paths=[("salary_max",)],
                    salary_text_paths=[("salary",)],
                    tags_paths=[("category",), ("categories",), ("tags",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

