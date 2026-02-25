"""
The Muse jobs provider.

Public API docs: https://www.themuse.com/developers/api/v2
This provider is opt-in and bounded by the orchestrator/provider allowlist.
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


THEMUSE_API_URL = "https://www.themuse.com/api/public/jobs"


def _decode_json_payload(text: str) -> dict:
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class TheMuseProvider(Provider):
    """Provider for The Muse API."""

    name = "themuse"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        params = {
            "page": 1,
            "descending": "true",
        }
        if criteria.primary_query:
            params["query"] = criteria.primary_query
        if criteria.location:
            params["location"] = criteria.location
        source_url = f"{THEMUSE_API_URL}?{urllib.parse.urlencode(params)}"

        headers = {"Accept": "application/json"}
        api_key = os.environ.get("JOBSCOUT_THEMUSE_API_KEY", "").strip()
        if api_key:
            headers["X-Api-Key"] = api_key

        result = await fetcher.fetch(source_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _decode_json_payload(result.text)
        raw_items = data.get("results")
        if not isinstance(raw_items, list):
            self.log_error("Unexpected response format")
            return []

        jobs: List[NormalizedJob] = []
        limit = max(1, min(criteria.max_results_per_source, len(raw_items)))
        for item in raw_items[:limit]:
            if not isinstance(item, dict):
                continue
            try:
                job = build_job(
                    item=item,
                    criteria=criteria,
                    source_name=self.name,
                    source_url=THEMUSE_API_URL,
                    id_paths=[("id",), ("refs", "id"), ("refs", "landing_page")],
                    title_paths=[("name",), ("title",)],
                    company_paths=[("company", "name"), ("company", "short_name"), ("company_name",)],
                    location_paths=[("locations",), ("location",), ("regions",)],
                    description_paths=[("contents",), ("description",)],
                    job_url_paths=[("refs", "landing_page"), ("refs", "job_page"), ("url",)],
                    apply_url_paths=[("refs", "landing_page"), ("refs", "job_page"), ("url",)],
                    posted_paths=[("publication_date",), ("created_at",), ("updated_at",)],
                    employment_paths=[("type",), ("levels",), ("type_name",)],
                    remote_hint_paths=[("locations",), ("type",)],
                    tags_paths=[("categories",), ("levels",), ("tags",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

