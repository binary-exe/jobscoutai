"""
Postgres storage adapter for JobScout.

Provides upsert operations optimized for Supabase Postgres.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg


# ==================== Schema ====================

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    provider_id TEXT,
    source TEXT NOT NULL,
    source_url TEXT,

    title TEXT NOT NULL,
    title_normalized TEXT,
    company TEXT NOT NULL,
    company_normalized TEXT,

    location_raw TEXT,
    country TEXT,
    city TEXT,
    remote_type TEXT DEFAULT 'unknown',

    employment_types TEXT[] DEFAULT '{}',
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,

    job_url TEXT,
    job_url_canonical TEXT,
    apply_url TEXT,

    description_text TEXT,

    emails TEXT[] DEFAULT '{}',
    company_website TEXT,
    linkedin_url TEXT,
    twitter_url TEXT,
    facebook_url TEXT,
    instagram_url TEXT,
    youtube_url TEXT,
    other_urls TEXT[] DEFAULT '{}',

    tags TEXT[] DEFAULT '{}',
    founder TEXT,

    posted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- AI fields
    ai_score REAL,
    ai_reasons TEXT,
    ai_remote_type TEXT,
    ai_employment_types TEXT[] DEFAULT '{}',
    ai_seniority TEXT,
    ai_confidence REAL,
    ai_summary TEXT,
    ai_requirements TEXT,
    ai_tech_stack TEXT,
    ai_company_domain TEXT,
    ai_company_summary TEXT,
    ai_flags TEXT[] DEFAULT '{}'
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_normalized);
CREATE INDEX IF NOT EXISTS idx_jobs_remote_type ON jobs(remote_type);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_ai_score ON jobs(ai_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_jobs_search ON jobs USING gin(to_tsvector('english', title || ' ' || company || ' ' || COALESCE(description_text, '')));

-- Runs table
CREATE TABLE IF NOT EXISTS runs (
    run_id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    jobs_collected INTEGER DEFAULT 0,
    jobs_new INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    jobs_filtered INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    sources TEXT,
    criteria JSONB
);
"""


async def init_schema(conn: asyncpg.Connection) -> None:
    """Initialize database schema."""
    await conn.execute(CREATE_JOBS_TABLE)


# ==================== Upsert Operations ====================

async def upsert_job_from_dict(
    conn: asyncpg.Connection,
    job: Dict[str, Any],
) -> Tuple[bool, bool]:
    """
    Upsert a job from a dictionary (e.g., from SQLite row).
    
    Returns (is_new, was_updated).
    """
    import json

    # Parse JSON arrays if coming from SQLite
    def parse_array(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return []
        return []

    # Check if exists
    existing = await conn.fetchval(
        "SELECT job_id FROM jobs WHERE job_id = $1",
        job["job_id"]
    )

    now = datetime.utcnow()

    if existing:
        # Update
        await conn.execute("""
            UPDATE jobs SET
                provider_id = $2,
                source = $3,
                source_url = $4,
                title = $5,
                title_normalized = $6,
                company = $7,
                company_normalized = $8,
                location_raw = $9,
                country = $10,
                city = $11,
                remote_type = $12,
                employment_types = $13,
                salary_min = $14,
                salary_max = $15,
                salary_currency = $16,
                job_url = $17,
                job_url_canonical = $18,
                apply_url = $19,
                description_text = $20,
                emails = $21,
                company_website = $22,
                linkedin_url = $23,
                twitter_url = $24,
                facebook_url = $25,
                instagram_url = $26,
                youtube_url = $27,
                other_urls = $28,
                tags = $29,
                founder = $30,
                posted_at = COALESCE($31, posted_at),
                expires_at = $32,
                last_seen_at = $33,
                ai_score = COALESCE($34, ai_score),
                ai_reasons = COALESCE($35, ai_reasons),
                ai_remote_type = COALESCE($36, ai_remote_type),
                ai_employment_types = COALESCE($37, ai_employment_types),
                ai_seniority = COALESCE($38, ai_seniority),
                ai_confidence = COALESCE($39, ai_confidence),
                ai_summary = COALESCE($40, ai_summary),
                ai_requirements = COALESCE($41, ai_requirements),
                ai_tech_stack = COALESCE($42, ai_tech_stack),
                ai_company_domain = COALESCE($43, ai_company_domain),
                ai_company_summary = COALESCE($44, ai_company_summary),
                ai_flags = COALESCE($45, ai_flags)
            WHERE job_id = $1
        """,
            job["job_id"],
            job.get("provider_id"),
            job.get("source", ""),
            job.get("source_url"),
            job.get("title", ""),
            job.get("title_normalized"),
            job.get("company", ""),
            job.get("company_normalized"),
            job.get("location_raw"),
            job.get("country"),
            job.get("city"),
            job.get("remote_type", "unknown"),
            parse_array(job.get("employment_types")),
            job.get("salary_min"),
            job.get("salary_max"),
            job.get("salary_currency"),
            job.get("job_url"),
            job.get("job_url_canonical"),
            job.get("apply_url"),
            job.get("description_text"),
            parse_array(job.get("emails")),
            job.get("company_website"),
            job.get("linkedin_url"),
            job.get("twitter_url"),
            job.get("facebook_url"),
            job.get("instagram_url"),
            job.get("youtube_url"),
            parse_array(job.get("other_urls")),
            parse_array(job.get("tags")),
            job.get("founder"),
            job.get("posted_at"),
            job.get("expires_at"),
            now,
            job.get("ai_score"),
            job.get("ai_reasons"),
            job.get("ai_remote_type"),
            parse_array(job.get("ai_employment_types")),
            job.get("ai_seniority"),
            job.get("ai_confidence"),
            job.get("ai_summary"),
            job.get("ai_requirements"),
            job.get("ai_tech_stack"),
            job.get("ai_company_domain"),
            job.get("ai_company_summary"),
            parse_array(job.get("ai_flags")),
        )
        return False, True
    else:
        # Insert
        await conn.execute("""
            INSERT INTO jobs (
                job_id, provider_id, source, source_url,
                title, title_normalized, company, company_normalized,
                location_raw, country, city, remote_type,
                employment_types, salary_min, salary_max, salary_currency,
                job_url, job_url_canonical, apply_url,
                description_text,
                emails, company_website,
                linkedin_url, twitter_url, facebook_url,
                instagram_url, youtube_url, other_urls,
                tags, founder,
                posted_at, expires_at, first_seen_at, last_seen_at,
                ai_score, ai_reasons, ai_remote_type, ai_employment_types,
                ai_seniority, ai_confidence, ai_summary, ai_requirements,
                ai_tech_stack, ai_company_domain, ai_company_summary, ai_flags
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                $31, $32, $33, $34, $35, $36, $37, $38, $39, $40,
                $41, $42, $43, $44, $45, $46
            )
        """,
            job["job_id"],
            job.get("provider_id"),
            job.get("source", ""),
            job.get("source_url"),
            job.get("title", ""),
            job.get("title_normalized"),
            job.get("company", ""),
            job.get("company_normalized"),
            job.get("location_raw"),
            job.get("country"),
            job.get("city"),
            job.get("remote_type", "unknown"),
            parse_array(job.get("employment_types")),
            job.get("salary_min"),
            job.get("salary_max"),
            job.get("salary_currency"),
            job.get("job_url"),
            job.get("job_url_canonical"),
            job.get("apply_url"),
            job.get("description_text"),
            parse_array(job.get("emails")),
            job.get("company_website"),
            job.get("linkedin_url"),
            job.get("twitter_url"),
            job.get("facebook_url"),
            job.get("instagram_url"),
            job.get("youtube_url"),
            parse_array(job.get("other_urls")),
            parse_array(job.get("tags")),
            job.get("founder"),
            job.get("posted_at"),
            job.get("expires_at"),
            now,
            now,
            job.get("ai_score"),
            job.get("ai_reasons"),
            job.get("ai_remote_type"),
            parse_array(job.get("ai_employment_types")),
            job.get("ai_seniority"),
            job.get("ai_confidence"),
            job.get("ai_summary"),
            job.get("ai_requirements"),
            job.get("ai_tech_stack"),
            job.get("ai_company_domain"),
            job.get("ai_company_summary"),
            parse_array(job.get("ai_flags")),
        )
        return True, False


async def start_run(conn: asyncpg.Connection, criteria_json: str = "") -> int:
    """Start a new scrape run and return its ID."""
    import json
    criteria = json.loads(criteria_json) if criteria_json else {}
    row = await conn.fetchrow(
        "INSERT INTO runs (criteria) VALUES ($1) RETURNING run_id",
        criteria
    )
    return row["run_id"]


async def finish_run(
    conn: asyncpg.Connection,
    run_id: int,
    jobs_collected: int,
    jobs_new: int,
    jobs_updated: int,
    jobs_filtered: int,
    errors: int,
    sources: str,
) -> None:
    """Finish a scrape run with statistics."""
    await conn.execute("""
        UPDATE runs SET
            finished_at = NOW(),
            jobs_collected = $2,
            jobs_new = $3,
            jobs_updated = $4,
            jobs_filtered = $5,
            errors = $6,
            sources = $7
        WHERE run_id = $1
    """, run_id, jobs_collected, jobs_new, jobs_updated, jobs_filtered, errors, sources)
