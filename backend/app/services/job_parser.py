"""
Job parsing service for Apply Workspace.

Fetches job URLs, extracts JSON-LD, and parses HTML as fallback.
"""

from typing import Dict, Optional, Any
from urllib.parse import urlparse
import re

from bs4 import BeautifulSoup

# Import from jobscout core library
from jobscout.fetchers.http import HttpFetcher
from jobscout.extract.jsonld import extract_job_postings_from_html
from jobscout.extract.html import strip_html
from jobscout.models import normalize_text, canonicalize_url


async def fetch_job_page(url: str) -> Dict[str, Any]:
    """
    Fetch a job page and return HTML and metadata.
    
    Returns:
        {
            "html": str,
            "status": int,
            "error": Optional[str],
            "content_type": str,
        }
    """
    async with HttpFetcher(timeout_s=15, max_retries=2) as fetcher:
        result = await fetcher.fetch(url, use_cache=False)
        
        return {
            "html": result.text if result.ok else "",
            "status": result.status,
            "error": result.error if not result.ok else None,
            "content_type": result.content_type,
        }


def extract_job_from_jsonld(html: str, url: str) -> Optional[Dict[str, Any]]:
    """
    Extract job data from JSON-LD JobPosting schema.
    
    Returns structured job data or None if not found.
    """
    jobs = extract_job_postings_from_html(html, source_url=url)
    if not jobs:
        return None
    
    # Use the first job found
    job = jobs[0]
    
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location_raw,
        "remote_type": job.remote_type.value if job.remote_type else None,
        "employment_type": [et.value for et in job.employment_types] if job.employment_types else [],
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "description_text": job.description_text,
        "job_url": job.job_url,
        "apply_url": job.apply_url,
        "company_website": job.company_website,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "tags": job.tags,
        "extracted_json": job.raw_data if hasattr(job, 'raw_data') else None,
        "extraction_method": "jsonld",
    }


def extract_job_from_html(html: str, url: str) -> Dict[str, Any]:
    """
    Extract job data from HTML using heuristics (fallback when JSON-LD not available).
    
    Returns structured job data with best-effort extraction.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # Extract title (try h1, meta title, og:title)
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = normalize_text(h1.get_text())
    if not title:
        meta_title = soup.find("meta", property="og:title") or soup.find("title")
        if meta_title:
            title = normalize_text(meta_title.get("content", "") or meta_title.get_text())
    
    # Extract company (try meta, og:site_name, or from URL)
    company = ""
    meta_company = soup.find("meta", property="og:site_name") or soup.find("meta", attrs={"name": "author"})
    if meta_company:
        company = normalize_text(meta_company.get("content", ""))
    if not company:
        # Try to extract from URL domain
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").split(".")[0]
        company = domain.capitalize() if domain else ""
    
    # Extract location (try meta, common selectors)
    location = ""
    meta_location = soup.find("meta", attrs={"name": "location"}) or soup.find("meta", property="og:locale")
    if meta_location:
        location = normalize_text(meta_location.get("content", ""))
    
    # Extract description (try meta description, main content)
    description_text = ""
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if meta_desc:
        description_text = normalize_text(meta_desc.get("content", ""))
    
    if not description_text:
        # Try to find main content area
        main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile("content|description|job", re.I))
        if main:
            description_text = strip_html(str(main))
            # Limit length
            if len(description_text) > 5000:
                description_text = description_text[:5000] + "..."
    
    # Extract apply URL (look for common patterns)
    apply_url = url
    apply_links = soup.find_all("a", href=re.compile(r"(apply|application|careers|jobs)", re.I))
    if apply_links:
        apply_href = apply_links[0].get("href", "")
        if apply_href:
            apply_url = canonicalize_url(apply_href, base_url=url)
    
    # Try to extract salary (look for common patterns)
    salary_min = None
    salary_max = None
    salary_currency = "USD"
    
    salary_text = soup.get_text()
    salary_match = re.search(r'\$?(\d{1,3}(?:,\d{3})*(?:k|K)?)\s*-\s*\$?(\d{1,3}(?:,\d{3})*(?:k|K)?)', salary_text)
    if salary_match:
        try:
            min_str = salary_match.group(1).replace(",", "").replace("k", "000").replace("K", "000")
            max_str = salary_match.group(2).replace(",", "").replace("k", "000").replace("K", "000")
            salary_min = float(min_str)
            salary_max = float(max_str)
        except ValueError:
            pass
    
    return {
        "title": title,
        "company": company,
        "location": location,
        "remote_type": None,  # Can't reliably detect from HTML alone
        "employment_type": [],
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "description_text": description_text,
        "job_url": url,
        "apply_url": apply_url,
        "company_website": "",
        "posted_at": None,
        "expires_at": None,
        "tags": [],
        "extracted_json": None,
        "extraction_method": "html",
    }


async def parse_job_url(url: str) -> Dict[str, Any]:
    """
    Parse a job URL and return structured job data.
    
    Tries JSON-LD first, falls back to HTML parsing.
    
    Returns:
        {
            "success": bool,
            "error": Optional[str],
            "data": Optional[Dict],
            "extraction_method": str,
        }
    """
    # Fetch the page
    fetch_result = await fetch_job_page(url)
    
    if fetch_result["error"]:
        return {
            "success": False,
            "error": fetch_result["error"],
            "data": None,
            "extraction_method": None,
        }
    
    html = fetch_result["html"]
    if not html:
        return {
            "success": False,
            "error": "No content retrieved",
            "data": None,
            "extraction_method": None,
        }
    
    # Try JSON-LD first
    job_data = extract_job_from_jsonld(html, url)
    if job_data:
        job_data["html"] = html  # Include HTML in response
        return {
            "success": True,
            "error": None,
            "data": job_data,
            "extraction_method": "jsonld",
        }
    
    # Fallback to HTML parsing
    job_data = extract_job_from_html(html, url)
    job_data["html"] = html  # Include HTML in response
    return {
        "success": True,
        "error": None,
        "data": job_data,
        "extraction_method": "html",
    }


def parse_job_text(text: str) -> Dict[str, Any]:
    """
    Parse job description text (when user pastes text instead of URL).
    
    Returns structured job data with minimal extraction.
    """
    # For text-only input, we can only extract what's explicitly in the text
    # Most fields will be empty and require user input
    
    # Try to extract title (first line or after "Title:", "Position:", etc.)
    title = ""
    lines = text.split("\n")
    for line in lines[:5]:  # Check first 5 lines
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in ["title:", "position:", "role:", "job title:"]):
            title = line.split(":", 1)[1].strip() if ":" in line else ""
            break
        elif line.strip() and len(line.strip()) < 100 and not title:
            # Assume first substantial line is title
            title = line.strip()
            break
    
    # Try to extract company
    company = ""
    for line in lines[:10]:
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in ["company:", "employer:", "organization:"]):
            company = line.split(":", 1)[1].strip() if ":" in line else ""
            break
    
    # Try to extract location
    location = ""
    for line in lines[:10]:
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in ["location:", "location:", "remote", "hybrid", "onsite"]):
            if ":" in line:
                location = line.split(":", 1)[1].strip()
            else:
                location = line.strip()
            break
    
    return {
        "title": title,
        "company": company,
        "location": location,
        "remote_type": None,
        "employment_type": [],
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "description_text": text,
        "job_url": None,
        "apply_url": None,
        "company_website": None,
        "posted_at": None,
        "expires_at": None,
        "tags": [],
        "extracted_json": None,
        "extraction_method": "text",
    }
