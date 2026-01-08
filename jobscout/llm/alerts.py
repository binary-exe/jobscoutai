"""
Quality and safety alert agent.

Identifies red flags in job postings: scams, suspicious domains,
missing apply flows, unrealistic claims, etc.
"""

from __future__ import annotations

import asyncio
import re
from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlsplit

from jobscout.models import NormalizedJob
from jobscout.llm.prompts import ALERTS_SYSTEM, build_alerts_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


# Quick heuristic checks (run without LLM)
SCAM_KEYWORDS = [
    "guaranteed income", "unlimited earning", "work from home stuffing envelopes",
    "get rich quick", "no experience required $100k",
    "advance fee", "wire transfer", "western union",
    "dm me for details", "click link in bio",
]

SUSPICIOUS_DOMAINS = [
    "bit.ly", "goo.gl", "tinyurl.com", "t.co",
    "linktr.ee", "beacons.ai",
]


def quick_alert_check(job: NormalizedJob) -> List[str]:
    """
    Quick heuristic alert check (no LLM needed).
    
    Returns list of flag codes.
    """
    flags: List[str] = []
    text = f"{job.title} {job.description_text}".lower()
    
    # Missing apply URL
    if not job.apply_url and not job.job_url:
        flags.append("missing_apply_url")
    
    # Check for scam keywords
    for kw in SCAM_KEYWORDS:
        if kw in text:
            flags.append("potential_scam")
            break
    
    # Check apply URL domain
    if job.apply_url:
        try:
            domain = urlsplit(job.apply_url).netloc.lower()
            if any(sus in domain for sus in SUSPICIOUS_DOMAINS):
                flags.append("suspicious_domain")
        except Exception:
            pass
    
    # Domain mismatch check
    if job.job_url and job.apply_url:
        try:
            job_domain = urlsplit(job.job_url).netloc.lower()
            apply_domain = urlsplit(job.apply_url).netloc.lower()
            # Normalize by removing www
            job_domain = job_domain.replace("www.", "")
            apply_domain = apply_domain.replace("www.", "")
            # Allow common ATS domains
            ats_domains = [
                "greenhouse.io", "lever.co", "ashbyhq.com", "workday.com",
                "smartrecruiters.com", "jobvite.com", "recruitee.com",
                "bamboohr.com", "workable.com",
            ]
            if job_domain != apply_domain:
                if not any(ats in apply_domain for ats in ats_domains):
                    # Could be suspicious, but LLM will verify
                    pass
        except Exception:
            pass
    
    # Unrealistic salary in title (quick check)
    salary_match = re.search(r"\$(\d{3,}),?(\d{3})?", job.title)
    if salary_match:
        try:
            salary = int(salary_match.group(1).replace(",", "") + (salary_match.group(2) or ""))
            if salary > 500000:  # $500k+ in title is suspicious
                flags.append("unrealistic_salary")
        except ValueError:
            pass
    
    return flags


async def check_job_quality(
    job: NormalizedJob,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    use_llm: bool = True,
) -> NormalizedJob:
    """
    Check job posting quality and safety.
    
    Combines quick heuristics with LLM analysis.
    
    Args:
        job: Job to check
        client: LLM client
        cache: Optional cache
        use_llm: Whether to use LLM (False = heuristics only)
        
    Returns:
        Job with ai_flags set
    """
    # Start with quick checks
    flags = quick_alert_check(job)
    severity = "none"
    
    if not use_llm:
        if flags:
            severity = "low" if len(flags) == 1 else "medium"
        job.ai_flags = flags
        return job
    
    # Use LLM for deeper analysis
    prompt = build_alerts_prompt(job)
    cache_key = client.cache_key(prompt, ALERTS_SYSTEM, "alerts")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _apply_alerts(job, cached.json_data, flags)
    
    # Call LLM
    response = await client.complete(prompt, ALERTS_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        # Fall back to heuristic flags only
        job.ai_flags = flags
        return job
    
    # Cache response
    if cache:
        cache.set(cache_key, response, job_id=job.job_id, step="alerts", prompt_hash=cache_key)
    
    return _apply_alerts(job, response.json_data, flags)


def _apply_alerts(job: NormalizedJob, data: dict, heuristic_flags: List[str]) -> NormalizedJob:
    """Apply alert data to job."""
    llm_flags = data.get("flags", [])
    if not isinstance(llm_flags, list):
        llm_flags = []
    
    # Combine heuristic and LLM flags (dedupe)
    all_flags = list(set(heuristic_flags + llm_flags))
    
    job.ai_flags = all_flags
    
    return job


async def check_jobs_batch(
    jobs: List[NormalizedJob],
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    use_llm: bool = True,
    max_jobs: int = 100,
) -> List[NormalizedJob]:
    """
    Check quality for multiple jobs.
    
    Args:
        jobs: Jobs to check
        client: LLM client
        cache: Optional cache
        use_llm: Whether to use LLM
        max_jobs: Maximum jobs for LLM analysis
        
    Returns:
        Jobs with alert flags
    """
    # Always run quick checks on all jobs
    for job in jobs:
        quick_flags = quick_alert_check(job)
        if quick_flags:
            job.ai_flags = quick_flags
    
    if not use_llm:
        return jobs
    
    # LLM analysis for subset
    to_process = jobs[:max_jobs]
    remaining = jobs[max_jobs:]
    
    semaphore = asyncio.Semaphore(5)
    
    async def check_one(job: NormalizedJob) -> NormalizedJob:
        async with semaphore:
            return await check_job_quality(job, client, cache, use_llm=True)
    
    tasks = [check_one(j) for j in to_process]
    checked = await asyncio.gather(*tasks)
    
    return list(checked) + remaining
