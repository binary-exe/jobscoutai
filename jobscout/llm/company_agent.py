"""
Company research agent.

Analyzes already-fetched job page content to extract and verify
company information without additional browsing.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, TYPE_CHECKING

from jobscout.models import NormalizedJob
from jobscout.llm.prompts import COMPANY_SYSTEM, build_company_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


async def analyze_company(
    job: NormalizedJob,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    page_content: Optional[str] = None,
) -> NormalizedJob:
    """
    Analyze company information from job content.
    
    Uses already-fetched page content to extract/verify company details.
    Does NOT make additional HTTP requests.
    
    Args:
        job: Job to analyze
        client: LLM client
        cache: Optional cache
        page_content: Additional page content (from enrichment fetch)
        
    Returns:
        Job with ai_company_domain, ai_company_summary set
    """
    prompt = build_company_prompt(job, page_content)
    cache_key = client.cache_key(prompt, COMPANY_SYSTEM, "company")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _apply_company_info(job, cached.json_data)
    
    # Call LLM
    response = await client.complete(prompt, COMPANY_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        return job
    
    # Cache response
    if cache:
        cache.set(cache_key, response, job_id=job.job_id, step="company", prompt_hash=cache_key)
    
    return _apply_company_info(job, response.json_data)


def _apply_company_info(job: NormalizedJob, data: dict) -> NormalizedJob:
    """Apply company research data to job."""
    # Company domain
    domain = data.get("company_domain")
    if domain and isinstance(domain, str):
        job.ai_company_domain = domain.strip().lower()
        # Update company_website if not already set
        if not job.company_website and domain:
            job.company_website = f"https://{domain}"
    
    # Company summary
    summary = data.get("company_summary")
    if summary and isinstance(summary, str):
        job.ai_company_summary = summary.strip()
    
    # Verified socials
    socials = data.get("verified_socials", {})
    if isinstance(socials, dict):
        if socials.get("linkedin") and not job.linkedin_url:
            job.linkedin_url = socials["linkedin"]
        if socials.get("twitter") and not job.twitter_url:
            job.twitter_url = socials["twitter"]
        if socials.get("github"):
            # Could add github_url field in future
            pass
    
    return job


async def analyze_companies_batch(
    jobs: List[NormalizedJob],
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    max_jobs: int = 100,
) -> List[NormalizedJob]:
    """
    Analyze companies for multiple jobs.
    
    Args:
        jobs: Jobs to analyze
        client: LLM client
        cache: Optional cache
        max_jobs: Maximum jobs to process
        
    Returns:
        Jobs with company info
    """
    to_process = jobs[:max_jobs]
    remaining = jobs[max_jobs:]
    
    semaphore = asyncio.Semaphore(5)
    
    async def analyze_one(job: NormalizedJob) -> NormalizedJob:
        async with semaphore:
            return await analyze_company(job, client, cache)
    
    tasks = [analyze_one(j) for j in to_process]
    analyzed = await asyncio.gather(*tasks)
    
    return list(analyzed) + remaining
