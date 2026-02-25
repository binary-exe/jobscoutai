"""
Careerjet API provider.

Endpoint docs are partner-oriented; this adapter is opt-in and requires
JOBSCOUT_CAREERJET_API_KEY.
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


CAREERJET_API_URL = "https://public.api.careerjet.net/search"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class CareerjetProvider(Provider):
    """Provider for Careerjet jobs API."""

    name = "careerjet"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        api_key = os.environ.get("JOBSCOUT_CAREERJET_API_KEY", "").strip()
        if not api_key:
            self.log_error("JOBSCOUT_CAREERJET_API_KEY not set")
            return []

        locale = os.environ.get("JOBSCOUT_CAREERJET_LOCALE_CODE", "en_GB").strip() or "en_GB"
        user_ip = os.environ.get("JOBSCOUT_CAREERJET_USER_IP", "").strip() or "127.0.0.1"
        user_agent = os.environ.get("JOBSCOUT_CAREERJET_USER_AGENT", "").strip() or "JobScoutBot/2.0"

        params = {
            "affid": api_key,
            "locale_code": locale,
            "user_ip": user_ip,
            "user_agent": user_agent,
            "keywords": criteria.primary_query,
            "location": criteria.location or "",
            "page": 1,
            "pagesize": max(1, min(criteria.max_results_per_source, 50)),
        }
        request_url = f"{CAREERJET_API_URL}?{urllib.parse.urlencode(params)}"

        result = await fetcher.fetch_json(request_url, use_cache=True)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
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
                    source_url=CAREERJET_API_URL,
                    id_paths=[("id",), ("jobid",), ("url",)],
                    title_paths=[("title",), ("jobtitle",)],
                    company_paths=[("company",), ("company_name",)],
                    location_paths=[("locations",), ("location",)],
                    description_paths=[("description",), ("snippet",)],
                    job_url_paths=[("url",), ("job_url",)],
                    apply_url_paths=[("url",), ("job_url",)],
                    posted_paths=[("date",), ("created",)],
                    employment_paths=[("contract_type",), ("job_type",)],
                    remote_hint_paths=[("locations",), ("title",)],
                    salary_text_paths=[("salary",)],
                    tags_paths=[("category",), ("categories",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

