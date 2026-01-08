"""
LLM-powered job ranking.

Scores and ranks jobs based on how well they match search criteria,
providing intelligent prioritization beyond keyword matching.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional, TYPE_CHECKING

from jobscout.models import Criteria, NormalizedJob
from jobscout.llm.prompts import RANK_SYSTEM, build_rank_prompt

if TYPE_CHECKING:
    from jobscout.llm.provider import LLMClient
    from jobscout.llm.cache import LLMCache


async def rank_jobs(
    jobs: List[NormalizedJob],
    criteria: Criteria,
    client: "LLMClient",
    cache: Optional["LLMCache"] = None,
    batch_size: int = 10,
    max_jobs: int = 100,
) -> List[NormalizedJob]:
    """
    Rank jobs by relevance to criteria using LLM.
    
    Args:
        jobs: Jobs to rank
        criteria: Search criteria
        client: LLM client
        cache: Optional cache
        batch_size: Jobs per LLM call (for efficiency)
        max_jobs: Maximum jobs to rank (cost control)
        
    Returns:
        Jobs sorted by AI score (descending), with ai_score and ai_reasons set
    """
    if not jobs:
        return jobs
    
    # Limit to max_jobs
    to_rank = jobs[:max_jobs]
    unranked = jobs[max_jobs:]
    
    # Process in batches
    batches = [to_rank[i:i + batch_size] for i in range(0, len(to_rank), batch_size)]
    
    ranked_jobs: List[NormalizedJob] = []
    
    for batch in batches:
        batch_result = await _rank_batch(batch, criteria, client, cache)
        ranked_jobs.extend(batch_result)
    
    # Sort by score descending
    ranked_jobs.sort(key=lambda j: j.ai_score or 0, reverse=True)
    
    # Add unranked jobs at the end (with score 0)
    for job in unranked:
        job.ai_score = 0
        job.ai_reasons = "Not ranked (exceeded max_jobs limit)"
    
    return ranked_jobs + unranked


async def _rank_batch(
    jobs: List[NormalizedJob],
    criteria: Criteria,
    client: "LLMClient",
    cache: Optional["LLMCache"],
) -> List[NormalizedJob]:
    """Rank a batch of jobs."""
    if not jobs:
        return jobs
    
    prompt = build_rank_prompt(criteria, jobs)
    
    # Generate cache key from batch
    job_ids = "|".join(j.job_id[:12] for j in jobs)
    cache_key = client.cache_key(prompt, RANK_SYSTEM, f"rank:{job_ids}")
    
    # Check cache
    if cache:
        cached = cache.get(cache_key)
        if cached and cached.json_data:
            return _apply_rankings(jobs, cached.json_data)
    
    # Call LLM
    response = await client.complete(prompt, RANK_SYSTEM, json_mode=True)
    
    if not response.ok or not response.json_data:
        # On failure, return jobs unranked
        return jobs
    
    # Cache response
    if cache:
        cache.set(cache_key, response, step="rank", prompt_hash=cache_key)
    
    return _apply_rankings(jobs, response.json_data)


def _apply_rankings(jobs: List[NormalizedJob], data: dict) -> List[NormalizedJob]:
    """Apply ranking data to jobs."""
    # Build lookup by job_id prefix
    job_map = {j.job_id[:12]: j for j in jobs}
    
    rankings = data.get("jobs", [])
    for rank_data in rankings:
        job_id_prefix = rank_data.get("id", "")[:12]
        if job_id_prefix in job_map:
            job = job_map[job_id_prefix]
            job.ai_score = float(rank_data.get("score", 0))
            reasons = rank_data.get("reasons", [])
            job.ai_reasons = "; ".join(reasons) if isinstance(reasons, list) else str(reasons)
    
    return jobs


async def quick_rank(
    jobs: List[NormalizedJob],
    criteria: Criteria,
    client: "LLMClient",
    top_n: int = 20,
) -> List[NormalizedJob]:
    """
    Quick ranking that only ranks top candidates.
    
    Pre-filters using heuristics, then LLM ranks the best candidates.
    More cost-efficient for large job sets.
    
    Args:
        jobs: All jobs
        criteria: Search criteria
        client: LLM client
        top_n: Number of top jobs to return
        
    Returns:
        Top N jobs ranked by AI
    """
    if len(jobs) <= top_n:
        return await rank_jobs(jobs, criteria, client)
    
    # Pre-score using heuristics
    def heuristic_score(job: NormalizedJob) -> float:
        score = 0.0
        blob = f"{job.title} {job.description_text}".lower()
        
        # Query match
        query_words = criteria.primary_query.lower().split()
        score += sum(10 for w in query_words if w in blob)
        
        # Must include
        score += sum(15 for kw in criteria.must_include if kw.lower() in blob)
        
        # Any include
        if criteria.any_include:
            if any(kw.lower() in blob for kw in criteria.any_include):
                score += 10
        
        # Must exclude penalty
        score -= sum(50 for kw in criteria.must_exclude if kw.lower() in blob)
        
        # Remote bonus
        if criteria.remote_only and job.remote_type.value == "remote":
            score += 20
        
        return score
    
    # Sort by heuristic and take top candidates
    candidates = sorted(jobs, key=heuristic_score, reverse=True)
    top_candidates = candidates[:min(top_n * 2, len(candidates))]
    
    # LLM rank the top candidates
    ranked = await rank_jobs(top_candidates, criteria, client, max_jobs=top_n * 2)
    
    return ranked[:top_n]
