"""
LLM-powered job enrichment.

Extracts structured information from job descriptions:
summaries, requirements, tech stack, salary notes.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, TYPE_CHECKING

from jobscout.models import NormalizedJob
from jobscout.llm.prompts import ENRICH_SYSTEM, build_enrich_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


async def enrich_job_with_llm(
    job: NormalizedJob,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
) -> NormalizedJob:
    """
    Enrich a job with LLM-extracted information.
    
    Args:
        job: Job to enrich
        client: LLM client
        cache: Optional cache
        
    Returns:
        Job with ai_summary, ai_requirements, ai_tech_stack set
    """
    if not job.description_text:
        return job
    
    prompt = build_enrich_prompt(job)
    cache_key = client.cache_key(prompt, ENRICH_SYSTEM, "enrich")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _apply_enrichment(job, cached.json_data)
    
    # Call LLM
    response = await client.complete(prompt, ENRICH_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        return job
    
    # Cache response
    if cache:
        cache.set(cache_key, response, job_id=job.job_id, step="enrich", prompt_hash=cache_key)
    
    return _apply_enrichment(job, response.json_data)


def _apply_enrichment(job: NormalizedJob, data: dict) -> NormalizedJob:
    """Apply enrichment data to job."""
    job.ai_summary = data.get("summary", "")
    
    requirements = data.get("requirements", [])
    if isinstance(requirements, list):
        job.ai_requirements = "; ".join(str(r) for r in requirements[:10])
    else:
        job.ai_requirements = str(requirements)
    
    tech_stack = data.get("tech_stack", [])
    if isinstance(tech_stack, list):
        job.ai_tech_stack = ", ".join(str(t) for t in tech_stack[:15])
    else:
        job.ai_tech_stack = str(tech_stack)
    
    # Salary notes
    salary_notes = data.get("salary_notes")
    if salary_notes:
        # Could be used to normalize salary fields in future
        pass
    
    return job


async def enrich_jobs_batch(
    jobs: List[NormalizedJob],
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    max_jobs: int = 100,
) -> List[NormalizedJob]:
    """
    Enrich multiple jobs with LLM.
    
    Args:
        jobs: Jobs to enrich
        client: LLM client
        cache: Optional cache
        max_jobs: Maximum jobs to process (cost control)
        
    Returns:
        Enriched jobs
    """
    # Limit to max_jobs
    to_process = jobs[:max_jobs]
    remaining = jobs[max_jobs:]
    
    # Process with bounded concurrency
    semaphore = asyncio.Semaphore(5)
    
    async def enrich_one(job: NormalizedJob) -> NormalizedJob:
        async with semaphore:
            return await enrich_job_with_llm(job, client, cache)
    
    tasks = [enrich_one(j) for j in to_process]
    enriched = await asyncio.gather(*tasks)
    
    return list(enriched) + remaining
