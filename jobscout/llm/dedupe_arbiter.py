"""
LLM-powered dedupe arbitration.

When heuristic deduplication is uncertain (near-threshold similarity),
uses LLM to make the final call on whether jobs are duplicates.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING

from jobscout.models import NormalizedJob
from jobscout.llm.prompts import build_dedupe_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


DEDUPE_SYSTEM = """You are a job posting deduplication expert. Determine if two job postings are for the same position.

Consider:
- Same company (accounting for name variations)
- Same or very similar job title
- Same or overlapping location
- Similar job responsibilities
- Posted around the same time

Output JSON with:
- same_job: true/false
- confidence: 0.0-1.0
- preferred: "A" or "B" (which posting has better/more complete information)
- reasoning: brief explanation"""


@dataclass
class DedupeDecision:
    """Result of LLM dedupe arbitration."""
    job_a: NormalizedJob
    job_b: NormalizedJob
    same_job: bool
    confidence: float
    preferred: str  # "A" or "B"
    reasoning: str


async def arbitrate_pair(
    job_a: NormalizedJob,
    job_b: NormalizedJob,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
) -> DedupeDecision:
    """
    Ask LLM whether two jobs are duplicates.
    
    Args:
        job_a: First job
        job_b: Second job
        client: LLM client
        cache: Optional cache
        
    Returns:
        DedupeDecision with LLM's determination
    """
    prompt = build_dedupe_prompt(job_a, job_b)
    cache_key = client.cache_key(prompt, DEDUPE_SYSTEM, "dedupe")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _parse_decision(job_a, job_b, cached.json_data)
    
    # Call LLM
    response = await client.complete(prompt, DEDUPE_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        # Default to not duplicates on failure
        return DedupeDecision(
            job_a=job_a,
            job_b=job_b,
            same_job=False,
            confidence=0.0,
            preferred="A",
            reasoning="LLM call failed",
        )
    
    # Cache response
    if cache:
        cache.set(
            cache_key, response,
            job_id=f"{job_a.job_id}:{job_b.job_id}",
            step="dedupe",
            prompt_hash=cache_key,
        )
    
    return _parse_decision(job_a, job_b, response.json_data)


def _parse_decision(job_a: NormalizedJob, job_b: NormalizedJob, data: dict) -> DedupeDecision:
    """Parse LLM response into DedupeDecision."""
    return DedupeDecision(
        job_a=job_a,
        job_b=job_b,
        same_job=bool(data.get("same_job", False)),
        confidence=float(data.get("confidence", 0.0)),
        preferred=str(data.get("preferred", "A")).upper(),
        reasoning=str(data.get("reasoning", "")),
    )


async def arbitrate_uncertain_pairs(
    pairs: List[Tuple[NormalizedJob, NormalizedJob]],
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    max_pairs: int = 20,
) -> List[DedupeDecision]:
    """
    Arbitrate multiple uncertain pairs.
    
    Args:
        pairs: List of (job_a, job_b) tuples
        client: LLM client
        cache: Optional cache
        max_pairs: Maximum pairs to process (cost control)
        
    Returns:
        List of DedupeDecision results
    """
    # Limit to max_pairs
    to_process = pairs[:max_pairs]
    
    semaphore = asyncio.Semaphore(3)  # Lower concurrency for dedupe
    
    async def arbitrate_one(pair: Tuple[NormalizedJob, NormalizedJob]) -> DedupeDecision:
        async with semaphore:
            return await arbitrate_pair(pair[0], pair[1], client, cache)
    
    tasks = [arbitrate_one(p) for p in to_process]
    return await asyncio.gather(*tasks)


def merge_duplicates(
    decisions: List[DedupeDecision],
    jobs: List[NormalizedJob],
) -> List[NormalizedJob]:
    """
    Merge duplicate jobs based on LLM decisions.
    
    For each pair determined to be duplicates, keeps the preferred one
    and removes the other.
    
    Args:
        decisions: LLM dedupe decisions
        jobs: Original job list
        
    Returns:
        Deduplicated job list
    """
    # Build set of job IDs to remove
    to_remove = set()
    
    for decision in decisions:
        if decision.same_job and decision.confidence >= 0.7:
            # Remove the non-preferred job
            if decision.preferred == "A":
                to_remove.add(decision.job_b.job_id)
            else:
                to_remove.add(decision.job_a.job_id)
    
    # Filter jobs
    return [j for j in jobs if j.job_id not in to_remove]
