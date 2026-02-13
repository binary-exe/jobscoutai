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
_DEFAULT_CORS_RAW = '["http://localhost:3000","https://jobscoutai.vercel.app"]'


def _parse_cors_origins(v: str) -> List[str]:
    """Parse CORS origins from env string (JSON or comma-separated). Never raises."""
    if not v or not isinstance(v, str):
        return ["http://localhost:3000", "https://jobscoutai.vercel.app"]
    v = v.strip()
    if not v:
        return ["http://localhost:3000", "https://jobscoutai.vercel.app"]
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
    return [v] if v else ["http://localhost:3000", "https://jobscoutai.vercel.app"]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "JobScout API"
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
    
    # Enabled providers (optional allowlist). If empty => use all built-in providers.
    # Default to stable sources: remotive, remoteok, arbeitnow, weworkremotely
    # NOTE: Union[...] prevents pydantic-settings from crashing on non-JSON env strings.
    enabled_providers: Union[str, List[str], None] = [
        "remotive",
        "remoteok",
        "arbeitnow",
        "weworkremotely",
        "workingnomads",
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
    openai_model: str = "gpt-4o-mini"
    ai_enabled: bool = False
    ai_max_jobs: int = 50  # Cost control

    # Premium AI (Apply Workspace add-ons; quota-gated + cached)
    premium_ai_enabled: bool = False
    premium_ai_max_tokens_interview: int = 1200
    premium_ai_max_tokens_template: int = 900

    # Apply Pack reviewer loop (premium-only; disabled by default)
    apply_pack_review_enabled: bool = False
    apply_pack_review_model: str = "gpt-4.1"
    apply_pack_review_max_iters: int = 2
    apply_pack_review_timeout_s: int = 20
    apply_pack_review_max_tokens_review: int = 900
    apply_pack_review_max_tokens_revise: int = 1400

    # Embeddings (pgvector personalization)
    embeddings_enabled: bool = False
    openai_embedding_model: str = "text-embedding-3-small"

    # Rate limiting
    max_results_per_page: int = 50

    # Paddle (payment processor)
    paddle_vendor_id: Optional[str] = None
    paddle_api_key: Optional[str] = None
    paddle_public_key: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_product_id: Optional[str] = None  # Product/Price ID for Pro subscription
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
