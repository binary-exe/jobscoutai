"""
Shared parsing helpers for HTTP JSON/XML provider adapters.

These utilities keep provider modules small and consistent while still
allowing each source to define its own field mappings.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional, Sequence

from jobscout.extract.html import strip_html
from jobscout.models import (
    Criteria,
    EmploymentType,
    NormalizedJob,
    RemoteType,
    canonicalize_url,
    normalize_text,
    now_utc,
    parse_date,
)


Path = Sequence[Any]


def get_path(data: Any, path: Path) -> Any:
    """Safely read a nested path from dict/list-like data."""
    cur = data
    for key in path:
        if isinstance(cur, dict):
            if key not in cur:
                return None
            cur = cur[key]
            continue
        if isinstance(cur, list) and isinstance(key, int):
            if key < 0 or key >= len(cur):
                return None
            cur = cur[key]
            continue
        return None
    return cur


def as_text(value: Any) -> str:
    """Convert mixed JSON values to readable normalized text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, (int, float, bool)):
        return normalize_text(str(value))
    if isinstance(value, dict):
        for key in ("name", "label", "title", "display_name", "value", "text"):
            if key in value:
                text = as_text(value.get(key))
                if text:
                    return text
        return normalize_text(json.dumps(value, ensure_ascii=False))
    if isinstance(value, list):
        parts = [as_text(v) for v in value[:8]]
        parts = [p for p in parts if p]
        return normalize_text(", ".join(parts))
    return normalize_text(str(value))


def first_text(data: Any, paths: Iterable[Path]) -> str:
    """Return the first non-empty text for any candidate path."""
    for p in paths:
        val = as_text(get_path(data, p))
        if val:
            return val
    return ""


def first_raw(data: Any, paths: Iterable[Path]) -> Any:
    """Return the first non-empty raw value for any candidate path."""
    for p in paths:
        val = get_path(data, p)
        if val is None:
            continue
        if isinstance(val, str) and not normalize_text(val):
            continue
        return val
    return None


def first_url(data: Any, paths: Iterable[Path]) -> str:
    """Return first canonicalized http(s) URL from candidate paths."""
    for p in paths:
        raw = as_text(get_path(data, p))
        if not raw:
            continue
        if raw.startswith(("http://", "https://")):
            return canonicalize_url(raw)
    return ""


def first_float(data: Any, paths: Iterable[Path]) -> Optional[float]:
    """Return first numeric field from candidate paths."""
    for p in paths:
        v = get_path(data, p)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            return float(v)
        text = as_text(v)
        if not text:
            continue
        m = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
        if not m:
            continue
        try:
            return float(m.group(0))
        except ValueError:
            continue
    return None


def salary_from_text(data: Any, paths: Iterable[Path]) -> tuple[Optional[float], Optional[float]]:
    """Extract salary bounds from a free-text field."""
    for p in paths:
        text = as_text(get_path(data, p))
        if not text:
            continue
        nums = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
        if not nums:
            continue
        try:
            parsed = [float(n.replace(",", "")) for n in nums[:2]]
        except ValueError:
            continue
        if len(parsed) == 1:
            return parsed[0], None
        return parsed[0], parsed[1]
    return None, None


def to_employment_types(value: Any) -> list[EmploymentType]:
    """Normalize arbitrary employment values into enum list."""
    parts: list[str] = []
    if value is None:
        return [EmploymentType.UNKNOWN]
    if isinstance(value, list):
        parts = [as_text(v) for v in value]
    elif isinstance(value, dict):
        parts = [as_text(v) for v in value.values()]
    else:
        parts = [as_text(value)]
    out: list[EmploymentType] = []
    for p in parts:
        if not p:
            continue
        et = EmploymentType.from_text(p)
        if et != EmploymentType.UNKNOWN:
            out.append(et)
    return out or [EmploymentType.UNKNOWN]


def to_tags(value: Any, limit: int = 8) -> list[str]:
    """Normalize arbitrary tag/category values into string list."""
    if value is None:
        return []
    if isinstance(value, list):
        tags = [as_text(v) for v in value]
    elif isinstance(value, dict):
        tags = [as_text(v) for v in value.values()]
    else:
        tags = [as_text(value)]
    clean = [t for t in tags if t]
    return clean[:limit]


def infer_remote_type(location_raw: str, hint: str, description: str, criteria: Criteria) -> RemoteType:
    """Infer remote type using location/hints/text with remote-only fallback."""
    merged = " ".join([location_raw, hint, description])
    inferred = RemoteType.from_text(merged)
    if inferred == RemoteType.UNKNOWN and criteria.remote_only:
        return RemoteType.REMOTE
    return inferred


def build_job(
    *,
    item: dict[str, Any],
    criteria: Criteria,
    source_name: str,
    source_url: str,
    id_paths: Iterable[Path],
    title_paths: Iterable[Path],
    company_paths: Iterable[Path],
    location_paths: Iterable[Path],
    description_paths: Iterable[Path],
    job_url_paths: Iterable[Path],
    apply_url_paths: Iterable[Path],
    posted_paths: Iterable[Path] = (),
    employment_paths: Iterable[Path] = (),
    remote_hint_paths: Iterable[Path] = (),
    salary_min_paths: Iterable[Path] = (),
    salary_max_paths: Iterable[Path] = (),
    salary_text_paths: Iterable[Path] = (),
    tags_paths: Iterable[Path] = (),
    company_site_paths: Iterable[Path] = (),
    currency_paths: Iterable[Path] = (),
) -> Optional[NormalizedJob]:
    """Build a NormalizedJob from mapped fields; returns None when invalid."""
    title = first_text(item, title_paths)
    company = first_text(item, company_paths) or "Unknown"
    if not title:
        return None

    provider_id = first_text(item, id_paths) or f"{company}:{title}"[:100]
    location_raw = first_text(item, location_paths) or (criteria.location or "Remote")
    description = first_text(item, description_paths)
    if "<" in description and ">" in description:
        description = strip_html(description)

    job_url = first_url(item, job_url_paths)
    apply_url = first_url(item, apply_url_paths) or job_url
    if not job_url and apply_url:
        job_url = apply_url
    if not job_url:
        return None

    posted_raw = first_raw(item, posted_paths)
    posted_at = parse_date(as_text(posted_raw))

    employment_raw = first_raw(item, employment_paths)
    employment_types = to_employment_types(employment_raw)

    remote_hint = first_text(item, remote_hint_paths)
    remote_type = infer_remote_type(location_raw, remote_hint, description, criteria)

    salary_min = first_float(item, salary_min_paths)
    salary_max = first_float(item, salary_max_paths)
    if salary_min is None and salary_max is None:
        parsed_min, parsed_max = salary_from_text(item, salary_text_paths)
        salary_min = parsed_min
        salary_max = parsed_max

    tags = to_tags(first_raw(item, tags_paths))
    company_website = first_url(item, company_site_paths)
    salary_currency = first_text(item, currency_paths)

    return NormalizedJob(
        provider_id=provider_id,
        scraped_at=now_utc(),
        posted_at=posted_at,
        source=source_name,
        source_url=source_url,
        title=title,
        company=company,
        location_raw=location_raw,
        remote_type=remote_type,
        employment_types=employment_types,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency or "",
        job_url=job_url,
        apply_url=apply_url or job_url,
        description_text=description,
        tags=tags,
        company_website=company_website,
        raw_data=item,
    )

