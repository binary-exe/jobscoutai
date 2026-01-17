"""
Application configuration via environment variables.
"""

import json
import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


# region agent log
_DEBUG_LOG_PATH = r"c:\Users\abdul\Desktop\jobscout\.cursor\debug.log"


def _agent_dbg(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    """Best-effort NDJSON debug logging for local dev; never raise."""
    try:
        parent = os.path.dirname(_DEBUG_LOG_PATH)
        if not parent or not os.path.isdir(parent):
            return
        payload = {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        return


# endregion


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

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "https://jobscoutai.vercel.app"]
    
    @model_validator(mode="before")
    @classmethod
    def parse_cors_origins_before(cls, data: Any) -> Any:
        """Parse CORS origins from environment variable before validation."""
        if isinstance(data, dict) and "cors_origins" in data:
            v = data["cors_origins"]
            if isinstance(v, str):
                # Try to parse as JSON first
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        data["cors_origins"] = parsed
                        return data
                except (json.JSONDecodeError, TypeError):
                    pass
                # Fallback: treat as comma-separated string
                if "," in v:
                    data["cors_origins"] = [origin.strip() for origin in v.split(",") if origin.strip()]
                    return data
                # Single value
                if v.strip():
                    data["cors_origins"] = [v.strip()]
                    return data
        return data
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try to parse as JSON first
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Fallback: treat as comma-separated string
            if "," in v:
                return [origin.strip() for origin in v.split(",") if origin.strip()]
            # Single value
            if v.strip():
                return [v.strip()]
        return ["http://localhost:3000", "https://jobscoutai.vercel.app"]

    @field_validator("scheduled_queries", mode="before")
    @classmethod
    def parse_scheduled_queries(cls, v: Any) -> List[str]:
        """Parse scheduled queries from JSON string or comma-separated list."""
        # region agent log
        _agent_dbg(
            "H_SCHEDULED_QUERIES_PARSE",
            "backend/app/core/config.py:parse_scheduled_queries",
            "validator_entry",
            {"value_type": type(v).__name__},
        )
        # endregion
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
        # region agent log
        _agent_dbg(
            "H_SCHEDULED_QUERIES_PARSE",
            "backend/app/core/config.py:parse_scheduled_queries",
            "validator_exit_default_empty",
            {},
        )
        # endregion
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
    
    # Enabled providers (optional allowlist). If empty => use all built-in providers.
    # Default to stable sources: remotive, remoteok, arbeitnow, weworkremotely
    # NOTE: Union[...] prevents pydantic-settings from crashing on non-JSON env strings.
    enabled_providers: Union[str, List[str], None] = ["remotive", "remoteok", "arbeitnow", "weworkremotely"]

    @field_validator("enabled_providers", mode="before")
    @classmethod
    def parse_enabled_providers(cls, v: Any) -> List[str]:
        """Parse enabled providers from JSON string or comma-separated list."""
        # region agent log
        _agent_dbg(
            "H_ENABLED_PROVIDERS_PARSE",
            "backend/app/core/config.py:parse_enabled_providers",
            "validator_entry",
            {
                "value_type": type(v).__name__,
                "value_len": len(v) if isinstance(v, str) else None,
            },
        )
        # endregion
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
        # region agent log
        _agent_dbg(
            "H_ENABLED_PROVIDERS_PARSE",
            "backend/app/core/config.py:parse_enabled_providers",
            "validator_exit_unexpected_type",
            {"value_type": type(v).__name__},
        )
        # endregion
        return []

    # AI settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    ai_enabled: bool = False
    ai_max_jobs: int = 50  # Cost control

    # Rate limiting
    max_results_per_page: int = 50

    # Paddle (payment processor)
    paddle_vendor_id: Optional[str] = None
    paddle_api_key: Optional[str] = None
    paddle_public_key: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_product_id: Optional[str] = None  # Product/Price ID for Pro subscription
    paddle_environment: str = "sandbox"  # sandbox or production

    class Config:
        env_prefix = "JOBSCOUT_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
