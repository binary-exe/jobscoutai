"""
Arbeitsamt (Bundesagentur fuer Arbeit) provider.

Uses OAuth client-credentials before calling the jobs API.
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


DEFAULT_ARBEITSAMT_TOKEN_URL = "https://rest.arbeitsagentur.de/oauth/gettoken_cc"
DEFAULT_ARBEITSAMT_API_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs"


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


class ArbeitsamtProvider(Provider):
    """Provider for Bundesagentur fuer Arbeit jobs API."""

    name = "arbeitsamt"

    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        self.reset_stats()

        client_id = os.environ.get("JOBSCOUT_ARBEITSAMT_CLIENT_ID", "").strip()
        client_secret = os.environ.get("JOBSCOUT_ARBEITSAMT_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            self.log_error("JOBSCOUT_ARBEITSAMT_CLIENT_ID / JOBSCOUT_ARBEITSAMT_CLIENT_SECRET not set")
            return []

        token_url = os.environ.get("JOBSCOUT_ARBEITSAMT_TOKEN_URL", DEFAULT_ARBEITSAMT_TOKEN_URL).strip() or DEFAULT_ARBEITSAMT_TOKEN_URL
        api_url = os.environ.get("JOBSCOUT_ARBEITSAMT_API_URL", DEFAULT_ARBEITSAMT_API_URL).strip() or DEFAULT_ARBEITSAMT_API_URL

        token_payload = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )
        token_headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        token_result = await fetcher.fetch(
            token_url,
            use_cache=False,
            headers=token_headers,
            method="POST",
            data=token_payload,
        )
        if not token_result.ok:
            self.log_error(f"Token request failed: {token_result.error or token_result.status}")
            return []

        token_data = token_result.json_data if isinstance(token_result.json_data, dict) else _parse_json(token_result.text)
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            self.log_error("OAuth token missing access_token")
            return []

        params = {
            "was": criteria.primary_query,
            "wo": criteria.location or "",
            "size": max(1, min(criteria.max_results_per_source, 100)),
            "page": 1,
        }
        request_url = f"{api_url}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        result = await fetcher.fetch(request_url, use_cache=True, headers=headers)
        if not result.ok:
            self.log_error(f"API request failed: {result.error or result.status}")
            return []

        data = result.json_data if isinstance(result.json_data, dict) else _parse_json(result.text)
        raw_items = data.get("stellenangebote")
        if not isinstance(raw_items, list):
            raw_items = data.get("jobs")
        if not isinstance(raw_items, list):
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
                    source_url=api_url,
                    id_paths=[("refnr",), ("stellenangebotsnummer",), ("id",)],
                    title_paths=[("titel",), ("beruf",), ("title",)],
                    company_paths=[("arbeitgeber", "name"), ("arbeitgeber",), ("company",)],
                    location_paths=[("arbeitsort", "ort"), ("arbeitsort", "region"), ("einsatzort",), ("location",)],
                    description_paths=[("aufgaben",), ("beschreibung",), ("description",)],
                    job_url_paths=[("externeUrl",), ("stellenangebotsort",), ("url",)],
                    apply_url_paths=[("bewerbung", "url"), ("externeUrl",), ("url",)],
                    posted_paths=[("aktuelleVeroeffentlichungsdatum",), ("eintrittsdatum",), ("posted_at",)],
                    employment_paths=[("arbeitszeitmodelle",), ("vertrag",), ("employment_type",)],
                    remote_hint_paths=[("telearbeit",), ("homeoffice",), ("arbeitsort", "ort")],
                    salary_min_paths=[("verdienst", "von"), ("salary_min",)],
                    salary_max_paths=[("verdienst", "bis"), ("salary_max",)],
                    salary_text_paths=[("verdienst", "betrag"), ("verdienst",)],
                    tags_paths=[("berufsfeld",), ("branche",), ("tags",)],
                )
                if job:
                    jobs.append(job)
            except Exception as e:
                self.log_error(f"Error parsing job: {e}")

        self.stats.collected = len(jobs)
        return jobs

