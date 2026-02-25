"""
Deterministic (non-AI) scoring utilities.

This module provides a lightweight relevance scoring function that can be used
to rank jobs without calling any LLMs. Scores are intended to be fast and
stable, and are stored as 0–100 floats.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Tuple

from jobscout.models import Criteria, NormalizedJob, RemoteType


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Keep this small; we only need to remove the most common noise words.
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall((text or "").lower())
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _safe_domain(url: str) -> str:
    if not url:
        return ""
    try:
        u = urllib.parse.urlsplit(url)
        host = (u.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


_AGGREGATOR_DOMAINS = {
    # Common aggregators / trackers / redirectors
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
    "simplyhired.com",
    "talent.com",
    "adzuna.com",
    "adzuna.co.uk",
    "jobviewtrack.com",
    "search.api.careerjet.net",
    "careerjet.net",
    "whatjobs.com",
    "juju.com",
    "reed.co.uk",
    "jobicy.com",
    "themuse.com",
}


def _is_likely_direct_apply(apply_url: str) -> bool:
    host = _safe_domain(apply_url)
    if not host:
        return False
    if host in _AGGREGATOR_DOMAINS:
        return False
    # Treat ATS domains as "direct enough"
    ats_signals = ("greenhouse.io", "lever.co", "ashbyhq.com", "workday.com", "myworkdayjobs.com")
    if host.endswith(ats_signals):
        return True
    # Unknown domain: assume direct
    return True


@dataclass(frozen=True)
class ScoreBreakdown:
    score: float
    reasons: List[str]


def score_job(job: NormalizedJob, criteria: Criteria) -> ScoreBreakdown:
    """
    Compute a deterministic relevance score (0–100) for a job relative to the scrape query.
    """
    q_tokens = _tokenize(criteria.primary_query)
    q_token_set = set(q_tokens)

    title_tokens = set(_tokenize(job.title))
    desc_tokens = set(_tokenize(job.description_text))

    contributions: List[Tuple[float, str]] = []
    score = 0.0

    # Title token match (0–55)
    if q_token_set:
        title_hits = len(q_token_set.intersection(title_tokens))
        title_ratio = title_hits / max(1, len(q_token_set))
        title_score = min(55.0, 55.0 * title_ratio)
        score += title_score
        if title_hits:
            contributions.append((title_score, "Strong title match"))

        # Description token match (0–25)
        desc_hits = len(q_token_set.intersection(desc_tokens))
        desc_ratio = desc_hits / max(1, len(q_token_set))
        desc_score = min(25.0, 25.0 * desc_ratio)
        score += desc_score
        if desc_hits:
            contributions.append((desc_score, "Matches keywords in description"))

    # Recency (0–10)
    if job.posted_at:
        now = datetime.now(timezone.utc)
        try:
            posted = job.posted_at
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            days = max(0.0, (now - posted).total_seconds() / 86400.0)
        except Exception:
            days = None

        recency_score = 0.0
        if days is not None:
            if days <= 3:
                recency_score = 10.0
            elif days <= 7:
                recency_score = 7.0
            elif days <= 30:
                recency_score = 4.0

        score += recency_score
        if recency_score >= 7:
            contributions.append((recency_score, "Recently posted"))

    # Remote alignment (0–5)
    if criteria.remote_only:
        remote_score = 0.0
        if job.remote_type == RemoteType.REMOTE:
            remote_score = 5.0
        elif job.remote_type == RemoteType.UNKNOWN:
            remote_score = 2.0
        score += remote_score
        if remote_score >= 5:
            contributions.append((remote_score, "Remote role"))

    # Direct-apply boost (0–5)
    direct_score = 0.0
    if job.apply_url and _is_likely_direct_apply(job.apply_url):
        direct_score = 5.0
        score += direct_score
        contributions.append((direct_score, "Direct/ATS apply link"))

    # Clamp
    score = max(0.0, min(100.0, score))

    reasons = [r for score_part, r in sorted(contributions, key=lambda x: x[0], reverse=True) if score_part > 0][:3]
    return ScoreBreakdown(score=score, reasons=reasons)


def apply_relevance_scoring(jobs: Iterable[NormalizedJob], criteria: Criteria) -> None:
    """
    Mutates jobs in-place to set `relevance_score` and `relevance_reasons`.
    """
    for j in jobs:
        breakdown = score_job(j, criteria)
        j.relevance_score = breakdown.score
        j.relevance_reasons = "; ".join(breakdown.reasons)

