"""
Robust JSON-LD extraction for JobPosting schema.org data.

Handles:
- Multiple script tags with different JSON-LD objects
- @graph containers
- Lists of objects
- Malformed JSON (trailing commas, JS-style comments)
- Nested structures
- Array fields (employmentType, jobLocation, etc.)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup

from jobscout.models import (
    NormalizedJob,
    RemoteType,
    EmploymentType,
    normalize_text,
    canonicalize_url,
    parse_date,
    now_utc,
)
from jobscout.extract.html import strip_html


def extract_jsonld_scripts(html: str) -> List[str]:
    """Extract all JSON-LD script contents from HTML."""
    if not html:
        return []

    scripts = []
    soup = BeautifulSoup(html, "lxml")

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        content = script.string
        if content:
            scripts.append(content.strip())

    return scripts


def clean_jsonld_string(s: str) -> str:
    """
    Clean malformed JSON-LD that might have JS artifacts.
    """
    # Remove JS-style single-line comments
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)

    # Remove JS-style multi-line comments
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)

    # Fix trailing commas before ] or }
    s = re.sub(r",\s*([\]}])", r"\1", s)

    # Fix unquoted keys (common JS mistake)
    # This is a simple heuristic, won't catch all cases
    s = re.sub(r"(?<=[{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'"\1":', s)

    return s


def parse_jsonld_tolerant(script_content: str) -> Any:
    """
    Parse JSON-LD with tolerance for common issues.
    """
    # Try direct parse first
    try:
        return json.loads(script_content)
    except json.JSONDecodeError:
        pass

    # Try cleaned version
    cleaned = clean_jsonld_string(script_content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try extracting just the object part (sometimes there's wrapper JS)
    match = re.search(r"(\{.*\}|\[.*\])", script_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def iter_jsonld_objects(data: Any) -> Iterable[Dict]:
    """
    Iterate through all objects in a JSON-LD structure.
    Handles @graph, lists, and nested structures.
    """
    if data is None:
        return

    if isinstance(data, list):
        for item in data:
            yield from iter_jsonld_objects(item)
    elif isinstance(data, dict):
        # Check for @graph container
        if "@graph" in data:
            yield from iter_jsonld_objects(data["@graph"])

        # Check for itemListElement (for search result pages)
        if "itemListElement" in data:
            for item in data.get("itemListElement", []):
                if isinstance(item, dict) and "item" in item:
                    yield from iter_jsonld_objects(item["item"])

        # Yield this object itself
        yield data

        # Also check nested objects that might contain JobPostings
        for key in ["mainEntity", "about", "hasPart"]:
            if key in data:
                yield from iter_jsonld_objects(data[key])


def is_job_posting(obj: Dict) -> bool:
    """Check if an object is a JobPosting."""
    obj_type = obj.get("@type", "")
    if isinstance(obj_type, list):
        return "JobPosting" in obj_type
    return obj_type == "JobPosting"


def extract_string(obj: Any, *keys: str, default: str = "") -> str:
    """Extract a string value from nested keys."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    if current is None:
        return default
    if isinstance(current, str):
        return normalize_text(current)
    if isinstance(current, list) and current:
        first = current[0]
        if isinstance(first, str):
            return normalize_text(first)
        if isinstance(first, dict):
            return normalize_text(first.get("name", "") or first.get("@value", ""))
    if isinstance(current, dict):
        return normalize_text(current.get("name", "") or current.get("@value", ""))
    return normalize_text(str(current))


def extract_location(obj: Dict) -> tuple[str, str, str, RemoteType]:
    """
    Extract location info from a JobPosting.
    Returns (raw_location, country, city, remote_type).
    """
    raw_parts = []
    country = ""
    city = ""
    remote_type = RemoteType.UNKNOWN

    # Check jobLocationType for remote indicator
    location_type = obj.get("jobLocationType", "")
    if isinstance(location_type, str) and "telecommute" in location_type.lower():
        remote_type = RemoteType.REMOTE

    # Check applicantLocationRequirements
    alr = obj.get("applicantLocationRequirements")
    if alr:
        if isinstance(alr, list):
            for item in alr:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    if name:
                        raw_parts.append(normalize_text(name))
        elif isinstance(alr, dict):
            name = alr.get("name", "")
            if name:
                raw_parts.append(normalize_text(name))

    # Check jobLocation
    job_loc = obj.get("jobLocation")
    if job_loc:
        locations = job_loc if isinstance(job_loc, list) else [job_loc]
        for loc in locations:
            if not isinstance(loc, dict):
                continue

            # Check @type for Place
            loc_type = loc.get("@type", "")

            # Extract address
            address = loc.get("address")
            if isinstance(address, dict):
                addr_locality = address.get("addressLocality", "")
                addr_region = address.get("addressRegion", "")
                addr_country = address.get("addressCountry", "")

                if isinstance(addr_country, dict):
                    addr_country = addr_country.get("name", "")

                if addr_locality:
                    city = normalize_text(addr_locality)
                    raw_parts.append(city)
                if addr_region:
                    raw_parts.append(normalize_text(addr_region))
                if addr_country:
                    country = normalize_text(addr_country)
                    raw_parts.append(country)
            elif isinstance(address, str):
                raw_parts.append(normalize_text(address))

            # Check for name
            loc_name = loc.get("name", "")
            if loc_name and loc_name not in raw_parts:
                raw_parts.append(normalize_text(loc_name))

    # Infer remote from location text
    raw_location = ", ".join(filter(None, raw_parts))
    if remote_type == RemoteType.UNKNOWN:
        remote_type = RemoteType.from_text(raw_location)

    return raw_location, country, city, remote_type


def extract_employment_types(obj: Dict) -> List[EmploymentType]:
    """Extract employment types from a JobPosting."""
    emp_type = obj.get("employmentType")
    return EmploymentType.from_schema_org(emp_type)


def extract_salary(obj: Dict) -> tuple[Optional[float], Optional[float], str]:
    """
    Extract salary information from a JobPosting.
    Returns (min, max, currency).
    """
    salary_min = None
    salary_max = None
    currency = ""

    base_salary = obj.get("baseSalary")
    if not base_salary:
        return salary_min, salary_max, currency

    if isinstance(base_salary, dict):
        currency = base_salary.get("currency", "")

        value = base_salary.get("value")
        if isinstance(value, dict):
            # MonetaryAmount with range
            min_val = value.get("minValue")
            max_val = value.get("maxValue")
            single_val = value.get("value")

            if min_val is not None:
                try:
                    salary_min = float(min_val)
                except (ValueError, TypeError):
                    pass
            if max_val is not None:
                try:
                    salary_max = float(max_val)
                except (ValueError, TypeError):
                    pass
            if single_val is not None and salary_min is None:
                try:
                    salary_min = salary_max = float(single_val)
                except (ValueError, TypeError):
                    pass
        elif isinstance(value, (int, float)):
            salary_min = salary_max = float(value)
        elif isinstance(value, str):
            try:
                salary_min = salary_max = float(value.replace(",", ""))
            except ValueError:
                pass

    return salary_min, salary_max, currency


def parse_job_posting(obj: Dict, source_url: str = "") -> Optional[NormalizedJob]:
    """
    Parse a JobPosting JSON-LD object into a NormalizedJob.
    """
    if not is_job_posting(obj):
        return None

    # Extract title
    title = extract_string(obj, "title") or extract_string(obj, "name")
    if not title:
        return None

    # Extract company
    hiring_org = obj.get("hiringOrganization", {})
    if isinstance(hiring_org, str):
        company = normalize_text(hiring_org)
        company_website = ""
        company_logo = ""
    elif isinstance(hiring_org, dict):
        company = extract_string(hiring_org, "name")
        company_website = canonicalize_url(
            hiring_org.get("sameAs", "") or hiring_org.get("url", "")
        )
        company_logo = hiring_org.get("logo", "")
        if isinstance(company_logo, dict):
            company_logo = company_logo.get("url", "")
    else:
        company = ""
        company_website = ""

    # Extract location
    raw_location, country, city, remote_type = extract_location(obj)

    # Extract employment types
    employment_types = extract_employment_types(obj)

    # Extract salary
    salary_min, salary_max, salary_currency = extract_salary(obj)

    # Extract dates
    posted_at = parse_date(obj.get("datePosted", ""))
    expires_at = parse_date(obj.get("validThrough", ""))

    # Extract URLs
    job_url = canonicalize_url(obj.get("url", "") or source_url)
    apply_url = canonicalize_url(
        obj.get("applicationContact", {}).get("url", "")
        if isinstance(obj.get("applicationContact"), dict) else ""
    ) or job_url

    # Direct apply might have different URL
    direct_apply = obj.get("directApply")
    if direct_apply and isinstance(obj.get("applicationContact"), dict):
        apply_url = canonicalize_url(obj["applicationContact"].get("url", "")) or apply_url

    # Extract description
    description_html = obj.get("description", "")
    description_text = strip_html(description_html) if description_html else ""

    # Extract identifier (provider_id)
    identifier = obj.get("identifier")
    provider_id = ""
    if isinstance(identifier, dict):
        provider_id = str(identifier.get("value", ""))
    elif isinstance(identifier, str):
        provider_id = identifier

    # Extract tags/skills
    tags = []
    skills = obj.get("skills") or obj.get("qualifications") or obj.get("experienceRequirements")
    if isinstance(skills, str):
        tags = [normalize_text(s) for s in skills.split(",") if s.strip()]
    elif isinstance(skills, list):
        tags = [normalize_text(str(s)) for s in skills if s]

    # Industry
    industry = obj.get("industry", "")
    if isinstance(industry, str) and industry:
        tags.append(normalize_text(industry))

    return NormalizedJob(
        provider_id=provider_id,
        scraped_at=now_utc(),
        posted_at=posted_at,
        expires_at=expires_at,
        source="schema_org",
        source_url=source_url,
        title=title,
        company=company or "Unknown",
        location_raw=raw_location,
        country=country,
        city=city,
        remote_type=remote_type,
        employment_types=employment_types,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        job_url=job_url,
        apply_url=apply_url,
        description_html=description_html,
        description_text=description_text,
        company_website=company_website,
        tags=tags[:20],
        raw_data=obj,
    )


def extract_job_postings_from_html(
    html: str,
    source_url: str = "",
) -> List[NormalizedJob]:
    """
    Extract all JobPosting objects from HTML.
    """
    jobs = []
    seen_ids = set()

    scripts = extract_jsonld_scripts(html)
    for script_content in scripts:
        data = parse_jsonld_tolerant(script_content)
        if data is None:
            continue

        for obj in iter_jsonld_objects(data):
            if not is_job_posting(obj):
                continue

            job = parse_job_posting(obj, source_url)
            if job and job.job_id not in seen_ids:
                seen_ids.add(job.job_id)
                jobs.append(job)

    return jobs

