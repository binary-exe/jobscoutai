"""
LLM integration for JobScout.

Provides AI-powered classification, ranking, enrichment,
company research, and quality/safety alerts.
"""

from jobscout.llm.provider import LLMClient, LLMConfig, get_llm_client
from jobscout.llm.classify import classify_job
from jobscout.llm.rank import rank_jobs
from jobscout.llm.enrich_llm import enrich_job_with_llm
from jobscout.llm.company_agent import analyze_company
from jobscout.llm.alerts import check_job_quality

__all__ = [
    "LLMClient",
    "LLMConfig",
    "get_llm_client",
    "classify_job",
    "rank_jobs",
    "enrich_job_with_llm",
    "analyze_company",
    "check_job_quality",
]
