"""
Enrichment utilities for extracting additional job/company information.

Features:
- Email extraction with obfuscation handling
- Social link extraction with proper URL resolution
- Founder/CEO name extraction
- Same-domain constraints to avoid polluting data
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from bs4 import BeautifulSoup

from jobscout.models import NormalizedJob, normalize_text, canonicalize_url

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


# ----------------------------- Email Extraction -----------------------------

# Standard email regex
EMAIL_PATTERN = re.compile(
    r"(?:mailto:)?([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE
)

# Common email obfuscation patterns
OBFUSCATED_PATTERNS = [
    # "user [at] domain [dot] com"
    re.compile(
        r"([A-Z0-9._%+-]+)\s*\[\s*at\s*\]\s*([A-Z0-9.-]+)\s*\[\s*dot\s*\]\s*([A-Z]{2,})",
        re.IGNORECASE
    ),
    # "user (at) domain (dot) com"
    re.compile(
        r"([A-Z0-9._%+-]+)\s*\(\s*at\s*\)\s*([A-Z0-9.-]+)\s*\(\s*dot\s*\)\s*([A-Z]{2,})",
        re.IGNORECASE
    ),
    # "user AT domain DOT com"
    re.compile(
        r"([A-Z0-9._%+-]+)\s+AT\s+([A-Z0-9.-]+)\s+DOT\s+([A-Z]{2,})",
        re.IGNORECASE
    ),
]

# Invalid email extensions (often false positives)
INVALID_EMAIL_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
}

# Common noreply/system emails to deprioritize
SYSTEM_EMAIL_PATTERNS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "webmaster",
    "support@", "info@", "contact@", "hello@",  # generic but OK as fallback
]


def is_valid_email(email: str) -> bool:
    """Check if an email looks valid."""
    email_lower = email.lower()

    # Check extension
    for ext in INVALID_EMAIL_EXTENSIONS:
        if email_lower.endswith(ext):
            return False

    # Basic structure check
    if email.count("@") != 1:
        return False

    local, domain = email.rsplit("@", 1)
    if not local or not domain:
        return False

    if "." not in domain:
        return False

    return True


def extract_emails(text: str) -> List[str]:
    """
    Extract email addresses from text, handling common obfuscation patterns.
    Returns emails sorted with likely real addresses first.
    """
    if not text:
        return []

    emails: Set[str] = set()

    # Standard pattern
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group(1).lower()
        if is_valid_email(email):
            emails.add(email)

    # Obfuscated patterns
    for pattern in OBFUSCATED_PATTERNS:
        for match in pattern.finditer(text):
            email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}".lower()
            if is_valid_email(email):
                emails.add(email)

    # Sort: personal emails first, then generic, then system
    def email_priority(e: str) -> int:
        e_lower = e.lower()
        # System/noreply emails last
        for pattern in SYSTEM_EMAIL_PATTERNS[:4]:  # noreply patterns
            if pattern in e_lower:
                return 3
        # Generic contact emails second
        for pattern in SYSTEM_EMAIL_PATTERNS[4:]:  # support/info/contact
            if e_lower.startswith(pattern):
                return 2
        # Personal/specific emails first
        return 1

    return sorted(emails, key=email_priority)


# ----------------------------- Social Link Extraction -----------------------------

# Social media domain to field mapping
SOCIAL_DOMAINS = {
    "linkedin.com": "linkedin_url",
    "twitter.com": "twitter_url",
    "x.com": "twitter_url",
    "facebook.com": "facebook_url",
    "instagram.com": "instagram_url",
    "youtube.com": "youtube_url",
    "youtu.be": "youtube_url",
    "reddit.com": "reddit_url",
    "github.com": "github_url",
    "glassdoor.com": "glassdoor_url",
}

# Domains to skip (job boards, tracking, etc.)
SKIP_DOMAINS = {
    "greenhouse.io", "lever.co", "workday.com", "smartrecruiters.com",
    "indeed.com", "linkedin.com/jobs", "glassdoor.com/job",
    "google.com", "goo.gl", "bit.ly", "t.co",
    "doubleclick.net", "googleadservices.com", "facebook.com/tr",
}


def resolve_url(href: str, base_url: str) -> str:
    """
    Resolve a potentially relative URL against a base URL.
    """
    if not href:
        return ""

    href = href.strip()

    # Already absolute
    if href.startswith(("http://", "https://", "//")):
        if href.startswith("//"):
            href = "https:" + href
        return href

    # Relative URL - resolve against base
    if base_url:
        try:
            return urllib.parse.urljoin(base_url, href)
        except Exception:
            pass

    return href


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urllib.parse.urlsplit(url)
        return parsed.netloc.lower().lstrip("www.")
    except Exception:
        return ""


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs are on the same domain (ignoring www)."""
    return get_domain(url1) == get_domain(url2)


def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped (tracking, job boards, etc.)."""
    domain = get_domain(url)
    for skip in SKIP_DOMAINS:
        if skip in domain:
            return True
    return False


def extract_social_links(
    html: str,
    base_url: str,
    restrict_to_domain: bool = True,
) -> Dict[str, str]:
    """
    Extract social media and company links from HTML.

    Args:
        html: HTML content
        base_url: URL of the page (for resolving relative links)
        restrict_to_domain: If True, only extract links that seem related to the company

    Returns:
        Dict mapping field names to URLs
    """
    result: Dict[str, str] = {
        "linkedin_url": "",
        "twitter_url": "",
        "facebook_url": "",
        "instagram_url": "",
        "youtube_url": "",
        "company_website": "",
    }
    other_urls: List[str] = []

    if not html:
        return result

    soup = BeautifulSoup(html, "lxml")
    base_domain = get_domain(base_url)

    # Look for links in footer, header, and social sections first (more reliable)
    priority_sections = soup.select("footer, header, [class*=social], [class*=footer], [class*=header]")
    all_links = []

    for section in priority_sections:
        all_links.extend(section.find_all("a", href=True))

    # Then add remaining links
    all_links.extend(soup.find_all("a", href=True))

    seen_urls: Set[str] = set()

    for a in all_links:
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "tel:", "mailto:")):
            continue

        # Resolve URL
        full_url = resolve_url(href, base_url)
        if not full_url:
            continue

        # Canonicalize
        canonical_url = canonicalize_url(full_url)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        # Skip tracking and job board URLs
        if should_skip_url(canonical_url):
            continue

        domain = get_domain(canonical_url)
        if not domain:
            continue

        # Check for social media
        matched = False
        for social_domain, field_name in SOCIAL_DOMAINS.items():
            if social_domain in domain:
                if not result[field_name]:
                    result[field_name] = canonical_url
                matched = True
                break

        if matched:
            continue

        # Check for company website
        # Company website is often linked from their job pages
        if not result["company_website"]:
            # Look for links that might be company homepage
            link_text = normalize_text(a.get_text()).lower()
            if any(x in link_text for x in ["website", "homepage", "about us", "company", "visit us"]):
                if domain != base_domain:  # Different from current page
                    result["company_website"] = canonical_url
                    continue

        # Collect other potentially useful URLs
        if not restrict_to_domain or domain == base_domain:
            if len(other_urls) < 20:
                other_urls.append(canonical_url)

    return result


# ----------------------------- Founder/CEO Extraction -----------------------------

FOUNDER_PATTERNS = [
    # "John Smith, Co-Founder"
    re.compile(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*,?\s*(?:Co-)?Founder", re.IGNORECASE),
    # "Co-Founder: John Smith"
    re.compile(r"(?:Co-)?Founder\s*[:\-]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})", re.IGNORECASE),
    # "CEO: John Smith"
    re.compile(r"CEO\s*[:\-]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})", re.IGNORECASE),
    # "John Smith, CEO"
    re.compile(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*,?\s*CEO", re.IGNORECASE),
    # "Founded by John Smith"
    re.compile(r"[Ff]ounded\s+by\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})", re.IGNORECASE),
]

# Names to exclude (common false positives)
EXCLUDED_NAMES = {
    "the company", "the ceo", "the founder", "our founder",
    "the team", "our team", "the board",
}


def guess_founder(text: str) -> str:
    """
    Try to extract founder/CEO name from text.
    """
    if not text:
        return ""

    for pattern in FOUNDER_PATTERNS:
        match = pattern.search(text)
        if match:
            name = normalize_text(match.group(1))
            if name.lower() not in EXCLUDED_NAMES:
                # Basic validation: should have at least 2 words
                if len(name.split()) >= 2:
                    return name

    return ""


# ----------------------------- Main Enrichment Function -----------------------------

async def enrich_job(
    job: NormalizedJob,
    fetcher: "HttpFetcher",
    max_pages: int = 2,
) -> NormalizedJob:
    """
    Enrich a job with additional information from its pages.

    Fetches job URL and apply URL to extract:
    - Email addresses
    - Social media links
    - Company website
    - Founder/CEO name
    """
    # First check if we already have emails in description
    if job.description_text and not job.emails:
        job.emails = extract_emails(job.description_text)

    # Collect pages to fetch
    pages_to_fetch = []
    if job.job_url:
        pages_to_fetch.append(job.job_url)
    if job.apply_url and job.apply_url != job.job_url:
        pages_to_fetch.append(job.apply_url)

    pages_fetched = 0

    for page_url in pages_to_fetch:
        if pages_fetched >= max_pages:
            break

        result = await fetcher.fetch(page_url, use_cache=True)
        if not result.ok:
            continue

        pages_fetched += 1
        html = result.text

        # Extract emails if we don't have any
        if not job.emails:
            job.emails = extract_emails(html)

        # Extract social links
        socials = extract_social_links(html, page_url, restrict_to_domain=False)

        # Update job fields if not already set
        if not job.linkedin_url and socials.get("linkedin_url"):
            job.linkedin_url = socials["linkedin_url"]
        if not job.twitter_url and socials.get("twitter_url"):
            job.twitter_url = socials["twitter_url"]
        if not job.facebook_url and socials.get("facebook_url"):
            job.facebook_url = socials["facebook_url"]
        if not job.instagram_url and socials.get("instagram_url"):
            job.instagram_url = socials["instagram_url"]
        if not job.youtube_url and socials.get("youtube_url"):
            job.youtube_url = socials["youtube_url"]
        if not job.company_website and socials.get("company_website"):
            job.company_website = socials["company_website"]

        # Try to find founder
        if not job.founder:
            from jobscout.extract.html import strip_html
            text = strip_html(html, max_len=15000)
            job.founder = guess_founder(text)

    return job

