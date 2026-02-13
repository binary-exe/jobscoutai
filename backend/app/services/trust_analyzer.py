"""
Trust Report analyzer for job postings.

Detects scam risk, ghost-likelihood, and staleness signals.
"""

from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone, timedelta
import re
import unicodedata
import os

from bs4 import BeautifulSoup
from jobscout.fetchers.http import HttpFetcher


# Scam indicators
SUSPICIOUS_EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com",
    "yandex.com", "mail.ru", "qq.com", "163.com",
]

SUSPICIOUS_KEYWORDS = [
    "work from home", "make money", "easy money", "quick cash",
    "no experience needed", "guaranteed income", "get rich",
    "upfront fee", "registration fee", "processing fee",
    "send money", "wire transfer", "western union", "moneygram",
    "crypto", "bitcoin", "ethereum", "paypal friends",
]

# Source-aware anti-spam tokens (legitimate boards use these, so down-weight them)
KNOWN_LEGITIMATE_TOKENS = {
    "remoteok": ["verify you're human", "remoteok verification"],
    "weworkremotely": ["weworkremotely"],
    "remotive": ["remotive"],
}

# Common boilerplate footers to strip
BOILERPLATE_FOOTERS = [
    r"equal opportunity employer",
    r"diversity.*inclusion",
    r"we are an equal opportunity",
    r"all qualified applicants",
    r"we do not discriminate",
    r"eoe.*aa",
    r"follow us on",
    r"connect with us",
    r"privacy policy",
    r"terms of service",
    r"cookie policy",
]

SCAM_PATTERNS = [
    r"whatsapp",
    r"telegram",
    r"signal",
    r"upfront.*fee",
    r"registration.*fee",
    r"send.*money",
    r"wire.*transfer",
    r"western.*union",
    r"moneygram",
    r"crypto.*payment",
    r"bitcoin.*payment",
]


# Ghost job indicators
GHOST_KEYWORDS = [
    "always hiring", "continuous recruitment", "ongoing opportunities",
    "talent pool", "future opportunities", "pipeline",
    "not currently hiring", "accepting applications",
]

GENERIC_DESCRIPTIONS = [
    "we are looking for", "join our team", "great opportunity",
    "competitive salary", "excellent benefits", "dynamic environment",
]

# Apply-link enrichment controls (cheap; no paid APIs)
def _int_env(name: str, default: int) -> int:
    try:
        v = int(os.getenv(name, str(default)).strip())
        return v
    except Exception:
        return default


APPLY_LINK_CACHE_TTL_HOURS = _int_env("JOBSCOUT_APPLY_LINK_CACHE_TTL_HOURS", 24)
APPLY_LINK_MAX_REDIRECTS = _int_env("JOBSCOUT_APPLY_LINK_MAX_REDIRECTS", 2)

URL_SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "short.link",
    "lnkd.in",
    "buff.ly",
    "ow.ly",
    "rebrand.ly",
    "rb.gy",
}


def extract_emails(text: str) -> List[str]:
    """Extract email addresses from text."""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text, re.IGNORECASE)
    return [email.lower() for email in emails]


def extract_phones(text: str) -> List[str]:
    """Extract phone numbers from text."""
    # Common phone patterns
    phone_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # US format
        r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',  # International
    ]
    phones = []
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        phones.extend(matches)
    return phones


def normalize_text(text: str) -> str:
    """Normalize unicode and strip boilerplate."""
    if not text:
        return ""
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    # Strip common boilerplate footers
    text_lower = text.lower()
    for pattern in BOILERPLATE_FOOTERS:
        text_lower = re.sub(pattern, "", text_lower, flags=re.IGNORECASE)
    return text.strip()


def extract_domain(url: Optional[str]) -> Optional[str]:
    """Extract domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix for consistency
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return None


def check_suspicious_links(text: str, html: Optional[str] = None) -> List[str]:
    """Check for suspicious links (WhatsApp, Telegram, etc.)."""
    suspicious = []
    text_lower = text.lower()
    
    # Check for messaging app links
    if re.search(r'whatsapp|wa\.me', text_lower, re.IGNORECASE):
        suspicious.append("Contains WhatsApp link")
    if re.search(r'telegram|t\.me', text_lower, re.IGNORECASE):
        suspicious.append("Contains Telegram link")
    if re.search(r'signal', text_lower, re.IGNORECASE):
        suspicious.append("Contains Signal link")
    
    # Check HTML for links if provided
    if html:
        soup = BeautifulSoup(html, "lxml")
        links = soup.find_all("a", href=True)
        for link in links:
            href = link.get("href", "").lower()
            if any(app in href for app in ["whatsapp", "wa.me", "telegram", "t.me", "signal"]):
                suspicious.append(f"Suspicious link found: {link.get('href', '')[:50]}")
    
    return suspicious


def analyze_scam_risk(
    job_url: Optional[str],
    description_text: Optional[str],
    html: Optional[str] = None,
    extracted_emails: Optional[List[str]] = None,
    extracted_phones: Optional[List[str]] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze scam risk signals.
    
    Returns:
        {
            "risk": "low" | "medium" | "high",
            "reasons": List[str],
            "score": int,  # 0-100, higher = more risky
        }
    """
    reasons = []
    score = 0
    
    # Normalize and clean text
    text = normalize_text(description_text or "")
    text_lower = text.lower()
    
    # Source-aware heuristics: down-weight known legitimate tokens
    source_weight = 1.0
    if source and source.lower() in KNOWN_LEGITIMATE_TOKENS:
        legitimate_tokens = KNOWN_LEGITIMATE_TOKENS[source.lower()]
        for token in legitimate_tokens:
            if token in text_lower:
                source_weight = 0.5  # Reduce weight for known legitimate sources
                break
    
    # Check for suspicious keywords
    found_keywords = []
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in text_lower:
            found_keywords.append(keyword)
            score += int(5 * source_weight)  # Apply source weight
    
    if found_keywords:
        reasons.append(f"Suspicious keywords found: {', '.join(found_keywords[:3])}")
    
    # Check for scam patterns
    found_patterns = []
    for pattern in SCAM_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            found_patterns.append(pattern)
            score += 10
    
    if found_patterns:
        reasons.append(f"Scam patterns detected: {', '.join(found_patterns[:2])}")
    
    # Check for suspicious links
    suspicious_links = check_suspicious_links(text, html)
    if suspicious_links:
        reasons.extend(suspicious_links[:3])
        score += 15 * len(suspicious_links)
    
    # Check email domains
    emails = extracted_emails or []
    if not emails and description_text:
        emails = extract_emails(description_text)
    
    suspicious_emails = [e for e in emails if any(domain in e for domain in SUSPICIOUS_EMAIL_DOMAINS)]
    if suspicious_emails:
        reasons.append(f"Suspicious email domains: {', '.join(suspicious_emails[:2])}")
        score += 10 * len(suspicious_emails)
    
    # Check for upfront fees
    if re.search(r'(upfront|registration|processing|application).*fee', text, re.IGNORECASE):
        reasons.append("Mentions upfront or processing fees")
        score += 20
    
    # Check for money transfer requests
    if re.search(r'(send|wire|transfer).*money', text, re.IGNORECASE):
        reasons.append("Requests money transfer")
        score += 25
    
    # Check URL for suspicious patterns
    if job_url:
        parsed = urlparse(job_url)
        domain = parsed.netloc.lower()
        
        # Check for suspicious domains
        if any(susp in domain for susp in ["bit.ly", "tinyurl", "short.link", "t.co"]):
            reasons.append("Uses URL shortener (could hide destination)")
            score += 5
        
        # Check for suspicious query parameters
        query_params = parse_qs(parsed.query)
        if any(key in query_params for key in ["ref", "affiliate", "partner"]):
            reasons.append("Contains affiliate/referral parameters")
            score += 3
    
    # Determine risk level
    if score >= 50:
        risk = "high"
    elif score >= 20:
        risk = "medium"
    else:
        risk = "low"
    
    # If no signals found, add a note
    if not reasons:
        reasons.append("No obvious scam signals detected")
    
    return {
        "risk": risk,
        "reasons": reasons[:5],  # Limit to top 5 reasons
        "score": min(100, score),
    }


def analyze_ghost_likelihood(
    description_text: Optional[str],
    posted_at: Optional[datetime] = None,
    job_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze ghost job likelihood.
    
    Ghost jobs are postings that aren't intended to be filled immediately
    or are used to build a talent pipeline.
    
    Returns:
        {
            "likelihood": "low" | "medium" | "high",
            "reasons": List[str],
            "score": int,  # 0-100, higher = more likely ghost
        }
    """
    reasons = []
    score = 0
    
    text = (description_text or "").lower()
    
    # Check for ghost keywords
    found_keywords = []
    for keyword in GHOST_KEYWORDS:
        if keyword in text:
            found_keywords.append(keyword)
            score += 10
    
    if found_keywords:
        reasons.append(f"Ghost job indicators: {', '.join(found_keywords[:2])}")
    
    # Check for generic descriptions
    generic_count = sum(1 for phrase in GENERIC_DESCRIPTIONS if phrase in text)
    if generic_count >= 2:
        reasons.append("Very generic job description")
        score += 15
    
    # Check if description is too short (might be a placeholder)
    if description_text and len(description_text.strip()) < 200:
        reasons.append("Very short job description (possible placeholder)")
        score += 10
    
    # Check if description lacks specific requirements
    if description_text:
        # Look for specific skills/requirements
        has_specifics = bool(re.search(r'(required|must have|experience with|proficient in)', text, re.IGNORECASE))
        if not has_specifics:
            reasons.append("Lacks specific job requirements")
            score += 5
    
    # Check posting date (very old postings might be ghost jobs)
    if posted_at:
        age_days = (datetime.now(timezone.utc) - posted_at).days
        if age_days > 180:
            reasons.append(f"Job posted {age_days} days ago (likely ghost or stale)")
            score += 20
        elif age_days > 90:
            reasons.append(f"Job posted {age_days} days ago (may be stale or ghost)")
            score += 10
    
    # Determine likelihood
    if score >= 40:
        likelihood = "high"
    elif score >= 15:
        likelihood = "medium"
    else:
        likelihood = "low"
    
    if not reasons:
        reasons.append("No obvious ghost job indicators")
    
    return {
        "likelihood": likelihood,
        "reasons": reasons[:5],
        "score": min(100, score),
    }


def analyze_staleness(
    job_url: Optional[str],
    description_text: Optional[str],
    posted_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    html: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze job posting staleness.
    
    Returns:
        {
            "score": int,  # 0-100, higher = more stale
            "reasons": List[str],
        }
    """
    reasons = []
    score = 0
    
    # Check posting date
    if posted_at:
        age_days = (datetime.now(timezone.utc) - posted_at).days
        if age_days > 180:
            reasons.append(f"Posted {age_days} days ago")
            score += 40
        elif age_days > 90:
            reasons.append(f"Posted {age_days} days ago")
            score += 20
        elif age_days > 30:
            reasons.append(f"Posted {age_days} days ago")
            score += 10
    else:
        reasons.append("No posting date found")
        score += 15
    
    # Check expiration date
    if expires_at:
        if expires_at < datetime.now(timezone.utc):
            reasons.append("Job posting has expired")
            score += 50
        else:
            days_until_expiry = (expires_at - datetime.now(timezone.utc)).days
            if days_until_expiry < 7:
                reasons.append(f"Expires in {days_until_expiry} days")
                score += 10
    else:
        # No expiry date might indicate stale posting
        if posted_at and (datetime.now(timezone.utc) - posted_at).days > 60:
            reasons.append("No expiration date and posting is old")
            score += 5
    
    # Check for "expired" or "closed" keywords in text
    if description_text:
        text_lower = description_text.lower()
        if re.search(r'(expired|closed|no longer|position filled)', text_lower):
            reasons.append("Text indicates position may be closed")
            score += 30
    
    # Check HTML for expired indicators
    if html:
        soup = BeautifulSoup(html, "lxml")
        page_text = soup.get_text().lower()
        if re.search(r'(expired|closed|no longer accepting|position filled)', page_text):
            reasons.append("Page indicates position may be closed")
            score += 25
    
    # Check if apply link might be broken (would need to actually test it)
    # For now, we just note if it's missing
    if not job_url:
        reasons.append("No job URL provided")
        score += 5
    
    return {
        "score": min(100, score),
        "reasons": reasons[:5],
    }


async def _test_apply_link(
    job_url: Optional[str],
    apply_url: Optional[str] = None,
    cache_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Test if apply link is valid by making an HTTP request (bounded).

    - Tests apply_url if provided, otherwise job_url.
    - Uses DB cache if available and fresh to avoid repeated checks.
    - Caps redirect chain to keep this cheap.
    
    Returns:
        {
            "status": "valid"|"broken"|"missing",
            "checked_url": Optional[str],
            "final_url": Optional[str],
            "redirects": int,
            "cached": bool,
            "checked_at": Optional[datetime],
            "warnings": List[str],
        }
    """
    # Prefer apply_url over job_url
    url_to_test = apply_url or job_url
    if not url_to_test:
        return {
            "status": "missing",
            "checked_url": None,
            "final_url": None,
            "redirects": 0,
            "cached": False,
            "checked_at": None,
            "warnings": [],
        }

    warnings: List[str] = []
    checked_at: Optional[datetime] = None

    # Heuristic warnings (no network)
    try:
        d = extract_domain(url_to_test)
        if d and d in URL_SHORTENER_DOMAINS:
            warnings.append("Apply link uses a URL shortener (destination is hidden)")
    except Exception:
        pass

    # Check cache first (if provided + fresh)
    if cache_result and "apply_link_status" in cache_result:
        cached_status = cache_result.get("apply_link_status")
        created_at = cache_result.get("created_at")
        if isinstance(created_at, datetime):
            checked_at = created_at
            try:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_ok = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)) <= timedelta(
                    hours=max(1, APPLY_LINK_CACHE_TTL_HOURS)
                )
            except Exception:
                age_ok = False
        else:
            age_ok = False

        if age_ok and cached_status in ["valid", "broken", "missing"]:
            return {
                "status": cached_status,
                "checked_url": url_to_test,
                "final_url": None,
                "redirects": 0,
                "cached": True,
                "checked_at": checked_at,
                "warnings": warnings,
            }

    # Test the URL with timeout and capped retries/redirects
    try:
        async with HttpFetcher(timeout_s=5, max_retries=1) as fetcher:
            result = await fetcher.fetch(
                url_to_test,
                use_cache=False,
                allow_redirects=True,
                max_redirects=max(0, APPLY_LINK_MAX_REDIRECTS),
                method="GET",
            )

            final_url = result.final_url
            redirects = int(result.redirect_count or 0)

            if redirects > 0:
                warnings.append(f"Apply link redirected {redirects} time(s)")

            # Some ATS systems return 401/403 to unauthenticated clients but are still "alive".
            if result.ok and result.status < 400:
                status = "valid"
            elif result.status in (401, 403):
                status = "valid"
                warnings.append(f"Apply link returned {result.status} (may require login)")
            elif result.status in (404, 410):
                status = "broken"
            else:
                status = "broken"

            # Destination-domain warning (cheap to show)
            try:
                start_domain = extract_domain(url_to_test)
                final_domain = extract_domain(final_url) if final_url else None
                if start_domain and final_domain and start_domain != final_domain:
                    warnings.append(f"Final destination domain differs ({start_domain} → {final_domain})")
            except Exception:
                pass

            return {
                "status": status,
                "checked_url": url_to_test,
                "final_url": final_url,
                "redirects": redirects,
                "cached": False,
                "checked_at": datetime.now(timezone.utc),
                "warnings": warnings[:6],
            }
    except Exception:
        warnings.append("Apply link check failed (timeout or network error)")
        return {
            "status": "broken",
            "checked_url": url_to_test,
            "final_url": None,
            "redirects": 0,
            "cached": False,
            "checked_at": datetime.now(timezone.utc),
            "warnings": warnings[:6],
        }


async def generate_trust_report(
    job_target_id: str,
    job_url: Optional[str],
    description_text: Optional[str],
    posted_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    html: Optional[str] = None,
    apply_url: Optional[str] = None,
    company_website: Optional[str] = None,
    source: Optional[str] = None,
    cached_trust_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a complete trust report for a job target.
    
    Returns:
        {
            "scam_risk": {...},
            "ghost_likelihood": {...},
            "staleness": {...},
            "domain": Optional[str],
            "extracted_emails": List[str],
            "extracted_phones": List[str],
            "apply_link_status": str,  # "valid", "broken", "missing"
        }
    """
    # Extract contact info
    emails = extract_emails(description_text or "")
    phones = extract_phones(description_text or "")
    
    # Extract domains
    job_domain = extract_domain(job_url)
    apply_domain = extract_domain(apply_url)
    company_domain = extract_domain(company_website)
    
    # Company/apply domain consistency check
    domain_mismatch_reasons = []
    domain_consistency_score = 100  # Start at 100, deduct for mismatches
    
    if company_domain and apply_domain:
        if company_domain != apply_domain:
            domain_mismatch_reasons.append(f"Company website domain ({company_domain}) differs from apply URL domain ({apply_domain})")
            domain_consistency_score -= 30
    elif company_domain and job_domain:
        if company_domain != job_domain:
            domain_mismatch_reasons.append(f"Company website domain ({company_domain}) differs from job URL domain ({job_domain})")
            domain_consistency_score -= 20
    
    # Analyze each aspect (with source-aware heuristics)
    scam_analysis = analyze_scam_risk(
        job_url=job_url,
        description_text=description_text,
        html=html,
        extracted_emails=emails,
        extracted_phones=phones,
        source=source,
    )
    
    ghost_analysis = analyze_ghost_likelihood(
        description_text=description_text,
        posted_at=posted_at,
        job_url=job_url,
    )
    
    staleness_analysis = analyze_staleness(
        job_url=job_url,
        description_text=description_text,
        posted_at=posted_at,
        expires_at=expires_at,
        html=html,
    )
    
    # Test apply link status (with caching)
    apply_link = await _test_apply_link(
        job_url=job_url,
        apply_url=apply_url,
        cache_result=cached_trust_report,
    )
    apply_link_status = apply_link.get("status") or "missing"
    
    # Calculate overall trust score (0-100, higher = more trustworthy)
    # Invert component scores so higher = better
    scam_inverted = 100 - min(100, scam_analysis["score"])
    ghost_inverted = 100 - min(100, ghost_analysis["score"])
    staleness_inverted = 100 - min(100, staleness_analysis["score"])
    link_score = 100 if apply_link_status == "valid" else (50 if apply_link_status == "missing" else 0)
    
    # Weighted average
    trust_score = (
        (scam_inverted * 0.35) +  # Scam risk is most important
        (ghost_inverted * 0.25) +  # Ghost likelihood
        (staleness_inverted * 0.20) +  # Staleness
        (link_score * 0.10) +  # Link health
        (domain_consistency_score * 0.10)  # Domain consistency
    )
    trust_score = max(0, min(100, int(trust_score)))
    
    return {
        "scam_risk": scam_analysis["risk"],
        "scam_reasons": scam_analysis["reasons"],
        "scam_score": scam_analysis["score"],
        "ghost_likelihood": ghost_analysis["likelihood"],
        "ghost_reasons": ghost_analysis["reasons"],
        "ghost_score": ghost_analysis["score"],
        "staleness_score": staleness_analysis["score"],
        "staleness_reasons": staleness_analysis["reasons"],
        "domain": job_domain,
        "extracted_emails": emails[:5],  # Limit to 5
        "extracted_phones": phones[:3],  # Limit to 3
        "apply_link_status": apply_link_status,
        "apply_link_final_url": apply_link.get("final_url"),
        "apply_link_redirects": apply_link.get("redirects", 0),
        "apply_link_cached": apply_link.get("cached", False),
        "apply_link_warnings": apply_link.get("warnings", []),
        "domain_consistency_reasons": domain_mismatch_reasons,
        "trust_score": trust_score,  # Overall trust score (0-100, higher = better)
    }
