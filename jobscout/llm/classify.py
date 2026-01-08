"""
LLM-powered job classification.

Accurately classifies remote type, employment type, and seniority
using LLM analysis of job content.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from jobscout.models import NormalizedJob, RemoteType, EmploymentType
from jobscout.llm.prompts import CLASSIFY_SYSTEM, build_classify_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


async def classify_job(
    job: NormalizedJob,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    update_fields: bool = True,
    confidence_threshold: float = 0.7,
) -> NormalizedJob:
    """
    Classify a job using LLM analysis.
    
    Args:
        job: Job to classify
        client: LLM client
        cache: Optional cache for responses
        update_fields: If True, update job fields when confidence is high
        confidence_threshold: Minimum confidence to update canonical fields
        
    Returns:
        Updated job with AI classification fields
    """
    prompt = build_classify_prompt(job)
    cache_key = client.cache_key(prompt, CLASSIFY_SYSTEM, "classify")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _apply_classification(job, cached.json_data, update_fields, confidence_threshold)
    
    # Call LLM
    response = await client.complete(prompt, CLASSIFY_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        return job
    
    # Cache response
    if cache:
        cache.set(cache_key, response, job_id=job.job_id, step="classify", prompt_hash=cache_key)
    
    return _apply_classification(job, response.json_data, update_fields, confidence_threshold)


def _apply_classification(
    job: NormalizedJob,
    data: dict,
    update_fields: bool,
    confidence_threshold: float,
) -> NormalizedJob:
    """Apply classification data to job."""
    confidence = data.get("confidence", 0.0)
    
    # Store AI classification
    job.ai_confidence = confidence
    job.ai_remote_type = data.get("remote_type", "")
    job.ai_employment_types = data.get("employment_types", [])
    job.ai_seniority = data.get("seniority", "")
    
    # Update canonical fields if confidence is high
    if update_fields and confidence >= confidence_threshold:
        # Remote type
        remote_map = {
            "remote": RemoteType.REMOTE,
            "hybrid": RemoteType.HYBRID,
            "onsite": RemoteType.ONSITE,
        }
        ai_remote = data.get("remote_type", "").lower()
        if ai_remote in remote_map:
            job.remote_type = remote_map[ai_remote]
        
        # Employment types
        ai_emp = data.get("employment_types", [])
        if ai_emp:
            emp_map = {
                "full_time": EmploymentType.FULL_TIME,
                "part_time": EmploymentType.PART_TIME,
                "contract": EmploymentType.CONTRACT,
                "freelance": EmploymentType.FREELANCE,
                "internship": EmploymentType.INTERNSHIP,
                "temporary": EmploymentType.TEMPORARY,
            }
            mapped = [emp_map.get(e.lower()) for e in ai_emp if e.lower() in emp_map]
            if mapped:
                job.employment_types = mapped
    
    return job


async def classify_jobs_batch(
    jobs: List[NormalizedJob],
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    update_fields: bool = True,
    confidence_threshold: float = 0.7,
    max_jobs: int = 100,
) -> List[NormalizedJob]:
    """
    Classify multiple jobs.
    
    Args:
        jobs: Jobs to classify
        client: LLM client
        cache: Optional cache
        update_fields: Update canonical fields when confident
        confidence_threshold: Minimum confidence for updates
        max_jobs: Maximum jobs to process (cost control)
        
    Returns:
        List of classified jobs
    """
    import asyncio
    
    # Limit to max_jobs
    to_process = jobs[:max_jobs]
    remaining = jobs[max_jobs:]
    
    # Process with bounded concurrency
    semaphore = asyncio.Semaphore(5)
    
    async def classify_one(job: NormalizedJob) -> NormalizedJob:
        async with semaphore:
            return await classify_job(job, client, cache, update_fields, confidence_threshold)
    
    tasks = [classify_one(j) for j in to_process]
    classified = await asyncio.gather(*tasks)
    
    # Return all jobs (classified + unprocessed)
    return list(classified) + remaining
