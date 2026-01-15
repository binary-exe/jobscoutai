"""
Trust Report analyzer for job postings.

Detects scam risk, ghost-likelihood, and staleness signals.
"""

from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import re

from bs4 import BeautifulSoup


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
    
    text = (description_text or "").lower()
    text_full = text
    
    # Check for suspicious keywords
    found_keywords = []
    for keyword in SUSPICIOUS_KEYWORDS:
        if keyword in text:
            found_keywords.append(keyword)
            score += 5
    
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
        if age_days > 90:
            reasons.append(f"Job posted {age_days} days ago (may be stale or ghost)")
            score += 10
        elif age_days > 180:
            reasons.append(f"Job posted {age_days} days ago (likely ghost or stale)")
            score += 20
    
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


async def _test_apply_link(job_url: Optional[str]) -> str:
    """
    Test if apply link is valid by making HTTP request.
    
    Returns: "valid", "broken", or "missing"
    """
    if not job_url:
        return "missing"
    
    try:
        async with HttpFetcher(timeout_s=5, max_retries=1) as fetcher:
            result = await fetcher.fetch(job_url, use_cache=False)
            
            if result.ok and result.status < 400:
                return "valid"
            elif result.status == 404:
                return "broken"
            else:
                return "broken"
    except Exception as e:
        # Timeout, connection error, etc.
        return "broken"


async def generate_trust_report(
    job_target_id: str,
    job_url: Optional[str],
    description_text: Optional[str],
    posted_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    html: Optional[str] = None,
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
    
    # Extract domain from URL
    domain = None
    if job_url:
        parsed = urlparse(job_url)
        domain = parsed.netloc
    
    # Analyze each aspect
    scam_analysis = analyze_scam_risk(
        job_url=job_url,
        description_text=description_text,
        html=html,
        extracted_emails=emails,
        extracted_phones=phones,
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
    
    # Test apply link status
    apply_link_status = await _test_apply_link(job_url)
    
    return {
        "scam_risk": scam_analysis["risk"],
        "scam_reasons": scam_analysis["reasons"],
        "scam_score": scam_analysis["score"],
        "ghost_likelihood": ghost_analysis["likelihood"],
        "ghost_reasons": ghost_analysis["reasons"],
        "ghost_score": ghost_analysis["score"],
        "staleness_score": staleness_analysis["score"],
        "staleness_reasons": staleness_analysis["reasons"],
        "domain": domain,
        "extracted_emails": emails[:5],  # Limit to 5
        "extracted_phones": phones[:3],  # Limit to 3
        "apply_link_status": apply_link_status,
    }
