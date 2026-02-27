"""
Application configuration via environment variables.
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings

_CORS_ENV = "JOBSCOUT_CORS_ORIGINS"
_DEFAULT_CORS_RAW = '["http://localhost:3000","https://jobiqueue.com","https://www.jobiqueue.com","https://jobscoutai.vercel.app"]'

# Scheduled query presets (broad job title lists for rotation).
SCHEDULED_QUERIES_PRESETS: Dict[str, List[str]] = {
    "tech_core_60": [
        "ai automation engineer", "automation engineer", "qa automation engineer", "sdet",
        "test automation engineer", "devops engineer", "site reliability engineer", "platform engineer",
        "cloud engineer", "backend engineer", "full stack engineer", "frontend engineer", "software engineer",
        "data engineer", "analytics engineer", "machine learning engineer", "mlops engineer", "ai engineer",
        "data scientist", "security engineer", "application security engineer", "solutions engineer",
        "sales engineer", "technical program manager", "product manager", "product designer", "ux designer",
        "technical writer", "mobile developer", "ios developer", "android developer", "react developer",
        "python developer", "java developer", "golang developer", "rust developer", "typescript developer",
        "database administrator", "network engineer", "system administrator", "infrastructure engineer",
        "quality assurance engineer", "qa engineer", "test engineer", "web developer", "full stack developer",
        "backend developer", "frontend developer", "junior developer", "senior developer", "staff engineer",
        "principal engineer", "engineering manager", "engineering director", "technical lead",
        "scrum master", "agile coach", "project manager", "release engineer", "data platform engineer",
    ],
    "tech_plus_120": [
        "ai automation engineer", "automation engineer", "qa automation engineer", "sdet",
        "test automation engineer", "devops engineer", "site reliability engineer", "platform engineer",
        "cloud engineer", "backend engineer", "full stack engineer", "frontend engineer", "software engineer",
        "data engineer", "analytics engineer", "machine learning engineer", "mlops engineer", "ai engineer",
        "data scientist", "security engineer", "application security engineer", "solutions engineer",
        "sales engineer", "technical program manager", "product manager", "product designer", "ux designer",
        "technical writer", "mobile developer", "ios developer", "android developer", "react developer",
        "python developer", "java developer", "golang developer", "rust developer", "typescript developer",
        "database administrator", "network engineer", "system administrator", "infrastructure engineer",
        "quality assurance engineer", "qa engineer", "test engineer", "web developer", "full stack developer",
        "backend developer", "frontend developer", "junior developer", "senior developer", "staff engineer",
        "principal engineer", "engineering manager", "engineering director", "technical lead",
        "scrum master", "agile coach", "project manager",
        # Extended set
        "kotlin developer", "swift developer", "nodejs developer", "ruby developer", "php developer",
        "c sharp developer", "dotnet developer", "aws engineer", "azure engineer", "gcp engineer",
        "kubernetes engineer", "terraform engineer", "data analyst", "business analyst", "product analyst",
        "ux researcher", "ui designer", "graphic designer", "content writer", "copywriter",
        "customer success manager", "account executive", "sales development representative",
        "marketing manager", "growth engineer", "seo specialist", "digital marketing",
        "support engineer", "technical support", "solutions architect", "system architect",
        "embedded engineer", "firmware engineer", "hardware engineer", "robotics engineer",
        "computer vision engineer", "nlp engineer", "research scientist", "quantitative analyst",
        "blockchain developer", "smart contract developer", "game developer", "unity developer",
        "unreal engine developer", "vr developer", "ar developer", "prompt engineer",
        "ai product manager", "data architect", "cloud architect", "security analyst",
        "penetration tester", "database engineer", "etl developer", "bi engineer",
        "power bi developer", "tableau developer", "salesforce developer", "sap developer",
        "qa lead", "devops architect", "observability engineer",
    ],
}


def _parse_cors_origins(v: str) -> List[str]:
    """Parse CORS origins from env string (JSON or comma-separated). Never raises."""
    if not v or not isinstance(v, str):
        return ["http://localhost:3000", "https://jobiqueue.com", "https://www.jobiqueue.com", "https://jobscoutai.vercel.app"]
    v = v.strip()
    if not v:
        return ["http://localhost:3000", "https://jobiqueue.com", "https://www.jobiqueue.com", "https://jobscoutai.vercel.app"]
    # Try JSON (double-quoted only)
    try:
        parsed = json.loads(v)
        if isinstance(parsed, list):
            return [x.strip() for x in parsed if isinstance(x, str) and x.strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    # Try single-quoted JSON (replace ' with " for valid JSON)
    try:
        normalized = v.replace("'", '"')
        parsed = json.loads(normalized)
        if isinstance(parsed, list):
            return [x.strip() for x in parsed if isinstance(x, str) and x.strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    # Comma-separated
    if "," in v:
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    return [v] if v else ["http://localhost:3000", "https://jobiqueue.com", "https://www.jobiqueue.com", "https://jobscoutai.vercel.app"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "JobiQueue API"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://localhost/jobscout"
    use_sqlite: bool = False  # For local dev
    sqlite_path: str = "jobs.db"

    # CORS: we read JOBSCOUT_CORS_ORIGINS from os.environ in validator so pydantic-settings
    # never tries to JSON-decode it (which crashes on Fly with single-quoted or empty value).
    cors_origins_raw: str = Field(
        default=_DEFAULT_CORS_RAW,
        description="JSON array or comma-separated origins",
    )

    @model_validator(mode="before")
    @classmethod
    def inject_cors_from_env(cls, data: Any) -> Any:
        # Read CORS from env ourselves so pydantic-settings never JSON-decodes it
        env_val = os.environ.get(_CORS_ENV)
        if env_val is not None and isinstance(data, dict):
            data["cors_origins_raw"] = env_val
        return data

    @computed_field
    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed CORS origins (do not name 'cors_origins' or env JOBSCOUT_CORS_ORIGINS is matched and JSON-decoded)."""
        return _parse_cors_origins(self.cors_origins_raw)

    @computed_field
    @property
    def resolved_scheduled_queries(self) -> List[str]:
        """Resolved list of scheduled queries: explicit list > preset > default_search_query."""
        queries = self.scheduled_queries if isinstance(self.scheduled_queries, list) else []
        if queries:
            return queries
        preset = (self.scheduled_queries_preset or "").strip().lower()
        if preset and preset in SCHEDULED_QUERIES_PRESETS:
            return SCHEDULED_QUERIES_PRESETS[preset]
        return [self.default_search_query]

    @field_validator("scheduled_queries", mode="before")
    @classmethod
    def parse_scheduled_queries(cls, v: Any) -> List[str]:
        """Parse scheduled queries from JSON string or comma-separated list."""
        if v is None:
            return []
        if isinstance(v, list):
            return [q for q in v if isinstance(q, str) and q.strip()]
        if isinstance(v, str):
            # Empty string
            if not v.strip():
                return []
            # Try JSON list first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [q for q in parsed if isinstance(q, str) and q.strip()]
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: comma-separated
            if "," in v:
                return [q.strip() for q in v.split(",") if q.strip()]
            # Single value
            return [v.strip()]
        return []

    # Admin
    admin_token: str = ""  # Required for POST /admin/run

    # Scraper settings
    scrape_interval_hours: int = 6
    default_search_query: str = "automation engineer"
    default_location: str = "Remote"
    # NOTE: Union[...] prevents pydantic-settings from crashing on non-JSON env strings.
    scheduled_queries: Union[str, List[str], None] = []
    # Preset name for scheduled queries when JOBSCOUT_SCHEDULED_QUERIES not set.
    # Options: tech_core_60 (~60 titles), tech_plus_120 (~120 titles).
    scheduled_queries_preset: Optional[str] = "tech_plus_120"
    # How many queries to run per scheduler tick (rotation).
    scheduled_queries_per_run: int = 2
    # Scheduled scrape caps (separate from public scrape).
    scheduled_scrape_max_results_per_source: int = 100
    scheduled_scrape_concurrency: int = 8

    # Public scrape settings
    public_scrape_enabled: bool = False
    public_scrape_max_concurrent: int = 2
    public_scrape_rate_limit_per_hour: int = 10
    public_scrape_default_location: str = "Remote"
    public_scrape_max_results_per_source: int = 100
    public_scrape_concurrency: int = 8

    # Enrichment controls (cost guardrails)
    # Default OFF to avoid per-job fanout; can be enabled explicitly via env for trusted/admin runs.
    scrape_enrich_company_pages: bool = False
    scrape_max_enrichment_pages: int = 2
    
    # SerpAPI Google Jobs (opt-in; add to JOBSCOUT_ENABLED_PROVIDERS)
    serpapi_api_key: Optional[str] = None
    serpapi_max_pages: int = 1

    # Optional aggregator/provider credentials (all opt-in via JOBSCOUT_ENABLED_PROVIDERS)
    themuse_api_key: Optional[str] = None
    careerjet_api_key: Optional[str] = None
    careerjet_locale_code: str = "en_GB"
    careerjet_user_ip: str = "127.0.0.1"
    careerjet_user_agent: str = "JobScoutBot/2.0"
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None
    adzuna_country: str = "gb"
    findwork_api_key: Optional[str] = None
    usajobs_api_key: Optional[str] = None
    usajobs_user_agent: Optional[str] = None
    reed_api_key: Optional[str] = None
    okjob_api_key: Optional[str] = None
    okjob_api_url: str = "https://okjob.io/api/jobs"
    jobs2careers_api_key: Optional[str] = None
    jobs2careers_api_url: str = "http://api.jobs2careers.com/api/jobsearch"
    whatjobs_api_key: Optional[str] = None
    whatjobs_api_url: str = "https://api.whatjobs.com/api/v1/jobs"
    juju_api_key: Optional[str] = None
    juju_api_url: str = "http://www.juju.com/publisher/jobs/"
    arbeitsamt_client_id: Optional[str] = None
    arbeitsamt_client_secret: Optional[str] = None
    arbeitsamt_token_url: str = "https://rest.arbeitsagentur.de/oauth/gettoken_cc"
    arbeitsamt_api_url: str = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs"
    # Optional taxonomy expansion (not a job feed).
    open_skills_api_url: Optional[str] = None

    # Enabled providers (optional allowlist). If empty => use all built-in providers.
    # Default: all built-in providers. Providers that need API keys will no-op until keys are set.
    # NOTE: Union[...] prevents pydantic-settings from crashing on non-JSON env strings.
    enabled_providers: Union[str, List[str], None] = [
        "remotive",
        "remoteok",
        "arbeitnow",
        "weworkremotely",
        "workingnomads",
        "remoteco",
        "justremote",
        "wellfound",
        "stackoverflow",
        "indeed",
        "flexjobs",
        "serpapi_google_jobs",
        "jobicy",
        "devitjobs_uk",
        "themuse",
        "careerjet",
        "adzuna",
        "findwork",
        "usajobs",
        "reed",
        "okjob",
        "jobs2careers",
        "whatjobs",
        "juju",
        "arbeitsamt",
    ]

    @field_validator("enabled_providers", mode="before")
    @classmethod
    def parse_enabled_providers(cls, v: Any) -> List[str]:
        """Parse enabled providers from JSON string or comma-separated list."""
        if v is None:
            return []
        if isinstance(v, list):
            return [p for p in v if isinstance(p, str) and p.strip()]
        if isinstance(v, str):
            # Empty string
            if not v.strip():
                return []
            # Try JSON list first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [p for p in parsed if isinstance(p, str) and p.strip()]
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: comma-separated
            if "," in v:
                return [p.strip() for p in v.split(",") if p.strip()]
            # Single value
            return [v.strip()]
        # Unexpected type - return empty list to use default
        return []

    # AI settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"
    ai_enabled: bool = True
    ai_max_jobs: int = 50  # Cost control

    # Premium AI (Apply Workspace add-ons; quota-gated + cached)
    premium_ai_enabled: bool = False
    premium_ai_max_tokens_interview: int = 1200
    premium_ai_max_tokens_template: int = 900

    # Apply Pack reviewer loop (premium-only)
    apply_pack_review_enabled: bool = True
    apply_pack_review_model: str = "gpt-4.1-mini"
    apply_pack_review_max_iters: int = 2
    apply_pack_review_timeout_s: int = 20
    apply_pack_review_max_tokens_review: int = 700
    apply_pack_review_max_tokens_revise: int = 1200

    # Embeddings (pgvector personalization)
    embeddings_enabled: bool = False
    openai_embedding_model: str = "text-embedding-3-small"

    # Second Brain (KB) RAG - authenticated per-user knowledge base
    kb_enabled: bool = False
    # Auto-index job_targets into KB when imported (opt-in; cap 50 per user)
    kb_auto_index_jobs: bool = False

    # Rate limiting
    max_results_per_page: int = 50

    # Paddle (payment processor)
    paddle_vendor_id: Optional[str] = None
    paddle_api_key: Optional[str] = None
    paddle_public_key: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_product_id: Optional[str] = None  # Product/Price ID for Pro subscription
    # New pricing (Standard/Pro; weekly/monthly)
    paddle_price_id_weekly_standard: Optional[str] = None
    paddle_price_id_weekly_pro: Optional[str] = None
    paddle_price_id_monthly_standard: Optional[str] = None
    # Keep paddle_price_id_monthly_pro for "monthly_pro" (current / latest)
    paddle_price_id_weekly_sprint: Optional[str] = None
    paddle_price_id_monthly_pro: Optional[str] = None
    paddle_price_id_monthly_power: Optional[str] = None
    paddle_price_id_annual_pro: Optional[str] = None
    paddle_price_id_annual_power: Optional[str] = None
    paddle_price_id_topup_20: Optional[str] = None
    paddle_environment: str = "sandbox"  # sandbox or production

    # Supabase (Auth)
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None

    class Config:
        env_prefix = "JOBSCOUT_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
