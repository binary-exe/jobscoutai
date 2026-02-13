"""
Core data models for JobScout.

Provides:
- Criteria: search parameters and runtime options
- NormalizedJob: canonical job representation with validated/normalized fields
- RemoteType / EmploymentType enums for structured classification
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ----------------------------- Enums -----------------------------

class RemoteType(str, Enum):
    """Normalized remote work classification."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"

    @classmethod
    def from_text(cls, text: str) -> "RemoteType":
        """Infer remote type from free-form text."""
        t = (text or "").lower()
        remote_signals = [
            "remote", "work from home", "wfh", "distributed",
            "anywhere", "telecommute", "home-based", "home based",
        ]
        hybrid_signals = ["hybrid", "flexible", "partial remote", "some remote"]
        onsite_signals = ["on-site", "onsite", "in-office", "in office", "office-based"]

        # Check hybrid first (more specific)
        if any(sig in t for sig in hybrid_signals):
            return cls.HYBRID
        if any(sig in t for sig in remote_signals):
            return cls.REMOTE
        if any(sig in t for sig in onsite_signals):
            return cls.ONSITE
        return cls.UNKNOWN


class EmploymentType(str, Enum):
    """Normalized employment type classification."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    VOLUNTEER = "volunteer"
    UNKNOWN = "unknown"

    @classmethod
    def from_text(cls, text: str) -> "EmploymentType":
        """Infer employment type from free-form text."""
        t = (text or "").lower()
        # Order matters: more specific patterns first
        if any(x in t for x in ["intern", "internship"]):
            return cls.INTERNSHIP
        if any(x in t for x in ["freelance", "freelancer", "gig"]):
            return cls.FREELANCE
        if any(x in t for x in ["contract", "contractor", "b2b", "1099"]):
            return cls.CONTRACT
        if any(x in t for x in ["temporary", "temp ", "seasonal"]):
            return cls.TEMPORARY
        if any(x in t for x in ["volunteer", "unpaid"]):
            return cls.VOLUNTEER
        if any(x in t for x in ["part-time", "part time", "parttime"]):
            return cls.PART_TIME
        if any(x in t for x in ["full-time", "full time", "fulltime", "permanent", "fte"]):
            return cls.FULL_TIME
        return cls.UNKNOWN

    @classmethod
    def from_schema_org(cls, value: Any) -> List["EmploymentType"]:
        """Parse schema.org employmentType (can be string or list)."""
        if not value:
            return [cls.UNKNOWN]
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = [str(v) for v in value]
        else:
            return [cls.UNKNOWN]

        results = []
        for v in values:
            v_lower = v.lower()
            if "full" in v_lower:
                results.append(cls.FULL_TIME)
            elif "part" in v_lower:
                results.append(cls.PART_TIME)
            elif "contract" in v_lower:
                results.append(cls.CONTRACT)
            elif "temporary" in v_lower:
                results.append(cls.TEMPORARY)
            elif "intern" in v_lower:
                results.append(cls.INTERNSHIP)
            elif "volunteer" in v_lower:
                results.append(cls.VOLUNTEER)
            else:
                et = cls.from_text(v)
                if et != cls.UNKNOWN:
                    results.append(et)
        return results if results else [cls.UNKNOWN]


# ----------------------------- Utilities -----------------------------

def normalize_text(s: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", (s or "")).strip()


def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication."""
    name = normalize_text(name)
    # Remove common suffixes
    suffixes = [
        r",?\s*(Inc\.?|LLC|Ltd\.?|Limited|Corp\.?|Corporation|GmbH|BV|B\.V\.|AG|SA|SAS|SRL|PLC)\.?\s*$"
    ]
    for suffix in suffixes:
        name = re.sub(suffix, "", name, flags=re.IGNORECASE)
    return normalize_text(name)


def canonicalize_url(url: str) -> str:
    """
    Canonicalize URL by removing tracking parameters and fragments.
    """
    if not url:
        return ""
    try:
        u = urllib.parse.urlsplit(url.strip())
        # Normalize scheme and host
        scheme = u.scheme.lower() or "https"
        netloc = u.netloc.lower()
        # Remove tracking params
        tracking_prefixes = ("utm_", "ref", "source", "campaign", "fbclid", "gclid", "mc_", "trk")
        q = urllib.parse.parse_qsl(u.query, keep_blank_values=False)
        q = [(k, v) for k, v in q if not any(k.lower().startswith(p) for p in tracking_prefixes)]
        new_q = urllib.parse.urlencode(q)
        # Remove fragment
        u = u._replace(scheme=scheme, netloc=netloc, query=new_q, fragment="")
        # Remove trailing slash from path (except for root)
        path = u.path.rstrip("/") if u.path != "/" else u.path
        u = u._replace(path=path)
        return urllib.parse.urlunsplit(u)
    except Exception:
        return url.strip()


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse various date formats into a datetime object.
    Returns None if parsing fails.
    """
    if not date_str:
        return None
    date_str = normalize_text(date_str)

    # Common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Try Unix timestamp (milliseconds)
    try:
        ts = int(date_str)
        if ts > 1e12:  # milliseconds
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError):
        pass

    return None


def now_utc() -> datetime:
    """Current UTC datetime."""
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    """Current UTC time as ISO string."""
    return now_utc().replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ----------------------------- Criteria -----------------------------

@dataclass
class Criteria:
    """Search criteria and runtime configuration."""

    # Search intent
    primary_query: str  # e.g. "AI Automation Engineer"
    must_include: List[str] = field(default_factory=list)  # AND match
    any_include: List[str] = field(default_factory=list)   # OR match
    must_exclude: List[str] = field(default_factory=list)  # Exclude

    # Location intent
    location: str = ""  # e.g. "Netherlands" / "Europe"
    remote_only: bool = True
    strict_remote: bool = False  # If True, exclude UNKNOWN remote type

    # Job type intent
    include_contract: bool = True
    include_freelance: bool = True
    include_full_time: bool = True
    include_part_time: bool = True
    include_internship: bool = False

    # Limits / behavior
    max_results_per_source: int = 200
    max_discovered_ats_tokens: int = 40
    max_search_results: int = 60
    enable_discovery: bool = False  # DuckDuckGo-based ATS discovery (optional; off by default)

    # Enrichment
    enrich_company_pages: bool = True
    max_enrichment_pages: int = 2  # per job
    request_timeout_s: int = 20
    concurrency: int = 12

    # Browser automation
    use_browser: bool = False
    browser_timeout_s: int = 30

    # Caching
    use_cache: bool = True
    cache_ttl_hours: int = 24

    def matches_employment_type(self, et: EmploymentType) -> bool:
        """Check if an employment type matches the criteria."""
        if et == EmploymentType.FULL_TIME:
            return self.include_full_time
        if et == EmploymentType.PART_TIME:
            return self.include_part_time
        if et == EmploymentType.CONTRACT:
            return self.include_contract
        if et == EmploymentType.FREELANCE:
            return self.include_freelance
        if et == EmploymentType.INTERNSHIP:
            return self.include_internship
        # For UNKNOWN/TEMPORARY/VOLUNTEER, default to including
        return True


# ----------------------------- NormalizedJob -----------------------------

@dataclass
class NormalizedJob:
    """
    Canonical job representation with validated and normalized fields.
    """

    # Identity
    job_id: str = ""  # Internal unique ID (computed)
    provider_id: str = ""  # ID from the source provider (if available)

    # Timestamps
    scraped_at: datetime = field(default_factory=now_utc)
    posted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Source info
    source: str = ""  # Provider name
    source_url: str = ""  # API/feed URL used

    # Core job info
    title: str = ""
    title_normalized: str = ""  # Lowercase, stripped
    company: str = ""
    company_normalized: str = ""  # For deduplication

    # Location
    location_raw: str = ""
    country: str = ""
    city: str = ""
    remote_type: RemoteType = RemoteType.UNKNOWN

    # Employment
    employment_types: List[EmploymentType] = field(default_factory=list)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = ""

    # URLs
    job_url: str = ""
    job_url_canonical: str = ""
    apply_url: str = ""

    # Description
    description_html: str = ""
    description_text: str = ""

    # Contact / social
    emails: List[str] = field(default_factory=list)
    company_website: str = ""
    linkedin_url: str = ""
    twitter_url: str = ""
    facebook_url: str = ""
    instagram_url: str = ""
    youtube_url: str = ""
    other_urls: List[str] = field(default_factory=list)

    # Extra
    tags: List[str] = field(default_factory=list)
    founder: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # AI-derived fields (populated when --ai is enabled)
    ai_score: Optional[float] = None  # 0-100 relevance score
    ai_reasons: str = ""  # Brief explanation of score
    ai_remote_type: str = ""  # LLM-classified remote type
    ai_employment_types: List[str] = field(default_factory=list)  # LLM-classified
    ai_seniority: str = ""  # intern/junior/mid/senior/lead/manager/executive
    ai_confidence: Optional[float] = None  # 0-1 confidence in classification
    ai_summary: str = ""  # Concise job summary
    ai_requirements: str = ""  # Key requirements (semicolon-separated)
    ai_tech_stack: str = ""  # Technologies mentioned (comma-separated)
    ai_company_domain: str = ""  # Likely company website domain
    ai_company_summary: str = ""  # Brief company description
    ai_flags: List[str] = field(default_factory=list)  # Quality/safety flags

    def __post_init__(self):
        """Normalize fields after initialization."""
        self.normalize()

    def normalize(self) -> None:
        """Normalize all fields for consistency and deduplication."""
        self.title = normalize_text(self.title)
        self.title_normalized = self.title.lower()
        self.company = normalize_text(self.company)
        self.company_normalized = normalize_company_name(self.company).lower()
        self.location_raw = normalize_text(self.location_raw)
        self.job_url = canonicalize_url(self.job_url)
        self.job_url_canonical = self.job_url
        self.apply_url = canonicalize_url(self.apply_url)
        self.company_website = canonicalize_url(self.company_website)

        # Ensure employment_types has at least UNKNOWN
        if not self.employment_types:
            self.employment_types = [EmploymentType.UNKNOWN]

        # Compute job_id if not set
        if not self.job_id:
            self.job_id = self.compute_job_id()

    def compute_job_id(self) -> str:
        """
        Compute a stable job ID for deduplication.
        Uses provider_id if available, otherwise hashes key fields.
        """
        if self.provider_id and self.source:
            # Provider-specific ID
            key = f"{self.source}:{self.provider_id}"
        else:
            # Hash-based ID from key fields
            key = "|".join([
                self.company_normalized,
                self.title_normalized,
                self.location_raw.lower(),
                self.job_url_canonical.lower(),
            ])
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    def matches_criteria(self, c: Criteria) -> bool:
        """Check if this job matches the search criteria."""
        blob = f"{self.title} {self.company} {self.location_raw} {self.description_text}".lower()

        # Remote filter
        if c.remote_only:
            if c.strict_remote:
                if self.remote_type != RemoteType.REMOTE:
                    return False
            else:
                # Accept REMOTE or UNKNOWN (benefit of doubt)
                if self.remote_type == RemoteType.ONSITE:
                    return False
                # Also check text for remote indicators
                if self.remote_type == RemoteType.UNKNOWN:
                    remote_indicators = ["remote", "work from home", "wfh", "distributed"]
                    if not any(ind in blob for ind in remote_indicators):
                        return False

        # Location filter
        if c.location:
            loc = c.location.lower()
            loc_found = loc in self.location_raw.lower() or loc in blob
            if loc == "europe":
                europe_indicators = ["europe", "eu", "eea", "european", "emea"]
                loc_found = loc_found or any(x in blob for x in europe_indicators)
            if not loc_found:
                return False

        # Exclusion filter
        for kw in c.must_exclude:
            if kw.lower() in blob:
                return False

        # Must-include filter (AND)
        for kw in c.must_include:
            if kw.lower() not in blob:
                return False

        # Any-include filter (OR)
        if c.any_include:
            if not any(kw.lower() in blob for kw in c.any_include):
                return False

        # Employment type filter
        if self.employment_types and self.employment_types[0] != EmploymentType.UNKNOWN:
            # Check if at least one employment type matches
            if not any(c.matches_employment_type(et) for et in self.employment_types):
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/export."""
        d = asdict(self)
        # Convert enums to strings
        d["remote_type"] = self.remote_type.value
        d["employment_types"] = [et.value for et in self.employment_types]
        # Convert datetimes to ISO strings
        d["scraped_at"] = self.scraped_at.isoformat() if self.scraped_at else ""
        d["posted_at"] = self.posted_at.isoformat() if self.posted_at else ""
        d["expires_at"] = self.expires_at.isoformat() if self.expires_at else ""
        # Flatten lists for CSV
        d["emails"] = "; ".join(self.emails)
        d["other_urls"] = " | ".join(self.other_urls[:10])
        d["tags"] = ", ".join(self.tags)
        # Flatten AI lists
        d["ai_employment_types"] = ", ".join(self.ai_employment_types) if self.ai_employment_types else ""
        d["ai_flags"] = ", ".join(self.ai_flags) if self.ai_flags else ""
        # Remove raw_data for export
        d.pop("raw_data", None)
        return d

    @classmethod
    def get_export_columns(cls) -> List[str]:
        """Get column order for CSV/Excel export."""
        return [
            "job_id", "scraped_at", "posted_at",
            "source", "title", "company",
            "location_raw", "country", "city", "remote_type",
            "employment_types", "salary_min", "salary_max", "salary_currency",
            "job_url", "apply_url",
            "description_text",
            "emails", "company_website",
            "linkedin_url", "twitter_url", "facebook_url",
            "tags", "founder",
            # AI fields
            "ai_score", "ai_reasons", "ai_seniority",
            "ai_summary", "ai_requirements", "ai_tech_stack",
            "ai_company_summary", "ai_flags",
        ]


# ----------------------------- Helper functions -----------------------------

def split_keywords(s: str) -> List[str]:
    """Split a comma/newline/semicolon-separated keyword string."""
    parts = re.split(r"[,\n;]+", s or "")
    cleaned = []
    for p in parts:
        p = normalize_text(p)
        p = p.strip("\"'")
        p = normalize_text(p)
        if not p or len(p) <= 1:
            continue
        cleaned.append(p)
    return cleaned

