"""
Prompt templates and utilities for LLM operations.

Contains system prompts and user prompt builders for each AI step.
"""

from __future__ import annotations

from typing import List, Optional

from jobscout.models import Criteria, NormalizedJob


# ===================== System Prompts =====================

CLASSIFY_SYSTEM = """You are a job classification expert. Analyze job postings and extract structured metadata.

Output JSON with these fields:
- remote_type: "remote" | "hybrid" | "onsite" | "unknown"
- employment_types: array of "full_time" | "part_time" | "contract" | "freelance" | "internship" | "temporary"
- seniority: "intern" | "junior" | "mid" | "senior" | "lead" | "manager" | "executive" | "unknown"
- confidence: 0.0-1.0 (how confident you are in the classification)
- reasoning: brief explanation

Be precise. Only say "remote" if truly remote. "Hybrid" means some office time required.
For seniority, look at title, years of experience mentioned, and responsibilities."""


RANK_SYSTEM = """You are a job matching expert. Score how well jobs match search criteria.

For each job, output JSON with:
- score: 0-100 (100 = perfect match)
- reasons: array of 2-4 brief reasons for the score

Scoring rubric:
- 40 pts: Role/title alignment with search query
- 25 pts: Remote/location compatibility  
- 20 pts: Skills/tech stack match with must_include/any_include keywords
- 15 pts: Seniority/experience level appropriateness

Penalize heavily for must_exclude keyword matches. Be strict but fair."""


ENRICH_SYSTEM = """You are a job analyst. Extract and summarize key information from job descriptions.

Output JSON with:
- summary: 2-3 sentence summary of the role
- requirements: array of 3-6 key requirements (skills, experience, etc.)
- tech_stack: array of technologies/tools mentioned
- salary_notes: any salary/compensation information found, or null

Be concise and accurate. Only include what's explicitly mentioned."""


COMPANY_SYSTEM = """You are a company research analyst. Extract company information from job pages and company content.

Output JSON with:
- company_domain: likely company website domain (e.g., "acme.com"), or null
- company_summary: 1-2 sentence description of what the company does
- verified_socials: object with linkedin/twitter/github URLs if found, or null for each

Only include information you can verify from the provided content."""


ALERTS_SYSTEM = """You are a job posting quality and safety analyst. Identify red flags in job postings.

Output JSON with:
- flags: array of flag codes (see below)
- severity: "none" | "low" | "medium" | "high"
- notes: brief explanation if any flags found

Flag codes:
- "missing_apply_url": No clear way to apply
- "suspicious_domain": Apply URL domain doesn't match company
- "crypto_scam": Crypto/NFT/Web3 red flags with unrealistic promises
- "pay_to_apply": Requires payment or purchase to apply
- "unrealistic_salary": Salary claims seem too good to be true
- "vague_description": Very vague about actual job duties
- "personal_info_request": Asks for SSN/bank info in posting
- "urgency_pressure": Excessive urgency tactics

Only flag genuine concerns. Most legitimate jobs will have no flags."""


# ===================== Prompt Builders =====================

def build_classify_prompt(job: NormalizedJob) -> str:
    """Build classification prompt for a single job."""
    return f"""Classify this job posting:

Title: {job.title}
Company: {job.company}
Location: {job.location_raw}
Tags: {', '.join(job.tags[:10]) if job.tags else 'None'}

Description (truncated):
{job.description_text[:3000]}

Respond with JSON only."""


def build_rank_prompt(criteria: Criteria, jobs: List[NormalizedJob]) -> str:
    """Build ranking prompt for a batch of jobs."""
    criteria_text = f"""Search Criteria:
- Query: {criteria.primary_query}
- Location: {criteria.location or 'Any'}
- Remote only: {criteria.remote_only}
- Must include: {', '.join(criteria.must_include) or 'None'}
- Any include: {', '.join(criteria.any_include) or 'None'}  
- Must exclude: {', '.join(criteria.must_exclude) or 'None'}
"""
    
    jobs_text = ""
    for i, job in enumerate(jobs):
        jobs_text += f"""
---
Job {i+1} (ID: {job.job_id[:12]}):
Title: {job.title}
Company: {job.company}
Location: {job.location_raw}
Remote: {job.remote_type.value}
Description snippet: {job.description_text[:500]}...
---
"""
    
    return f"""{criteria_text}

Score these jobs (0-100) based on how well they match the criteria:
{jobs_text}

Respond with JSON: {{"jobs": [{{"id": "...", "score": N, "reasons": [...]}}]}}"""


def build_enrich_prompt(job: NormalizedJob) -> str:
    """Build enrichment prompt for a single job."""
    return f"""Analyze this job posting and extract key information:

Title: {job.title}
Company: {job.company}

Full Description:
{job.description_text[:4000]}

Respond with JSON only."""


def build_company_prompt(
    job: NormalizedJob,
    page_content: Optional[str] = None,
) -> str:
    """Build company research prompt."""
    content = page_content or job.description_text
    
    return f"""Research this company based on the job posting content:

Company name: {job.company}
Job URL: {job.job_url}
Current website field: {job.company_website or 'Unknown'}

Page content (truncated):
{content[:3000]}

Respond with JSON only."""


def build_alerts_prompt(job: NormalizedJob) -> str:
    """Build quality/safety alerts prompt."""
    return f"""Check this job posting for quality and safety issues:

Title: {job.title}
Company: {job.company}
Job URL: {job.job_url}
Apply URL: {job.apply_url}
Location: {job.location_raw}
Remote type: {job.remote_type.value}

Description:
{job.description_text[:3000]}

Respond with JSON only."""


def build_dedupe_prompt(job1: NormalizedJob, job2: NormalizedJob) -> str:
    """Build dedupe arbitration prompt for two jobs."""
    return f"""Are these two job postings for the same position?

Job A:
- Title: {job1.title}
- Company: {job1.company}
- Location: {job1.location_raw}
- URL: {job1.job_url}
- Posted: {job1.posted_at}
- Description snippet: {job1.description_text[:500]}

Job B:
- Title: {job2.title}
- Company: {job2.company}
- Location: {job2.location_raw}
- URL: {job2.job_url}
- Posted: {job2.posted_at}
- Description snippet: {job2.description_text[:500]}

Respond with JSON:
{{
  "same_job": true/false,
  "confidence": 0.0-1.0,
  "preferred": "A" or "B" (which has better/more complete info),
  "reasoning": "brief explanation"
}}"""
