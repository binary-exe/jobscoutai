"""
SQLite-based job storage with upserts and run tracking.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from jobscout.models import NormalizedJob, now_utc_iso


@dataclass
class RunStats:
    """Statistics for a scrape run."""
    run_id: int
    started_at: str
    finished_at: Optional[str] = None
    jobs_collected: int = 0
    jobs_new: int = 0
    jobs_updated: int = 0
    jobs_filtered: int = 0
    errors: int = 0
    sources: str = ""


class JobDatabase:
    """
    SQLite database for storing jobs with upsert support.
    """

    def __init__(self, db_path: str):
        """
        Initialize the database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection (creating if needed)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._lock:
            conn = self._get_conn()
            conn.executescript("""
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
                    remote_type TEXT,
                    
                    employment_types TEXT,  -- JSON array
                    salary_min REAL,
                    salary_max REAL,
                    salary_currency TEXT,
                    
                    job_url TEXT,
                    job_url_canonical TEXT,
                    apply_url TEXT,
                    
                    description_text TEXT,
                    
                    emails TEXT,  -- JSON array
                    company_website TEXT,
                    linkedin_url TEXT,
                    twitter_url TEXT,
                    facebook_url TEXT,
                    instagram_url TEXT,
                    youtube_url TEXT,
                    other_urls TEXT,  -- JSON array
                    
                    tags TEXT,  -- JSON array
                    founder TEXT,
                    
                    posted_at TEXT,
                    expires_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    
                    raw_data TEXT,  -- JSON

                    -- Deterministic relevance fields (non-AI)
                    relevance_score REAL,
                    relevance_reasons TEXT,
                    
                    -- AI-derived fields
                    ai_score REAL,
                    ai_reasons TEXT,
                    ai_remote_type TEXT,
                    ai_employment_types TEXT,  -- JSON array
                    ai_seniority TEXT,
                    ai_confidence REAL,
                    ai_summary TEXT,
                    ai_requirements TEXT,
                    ai_tech_stack TEXT,
                    ai_company_domain TEXT,
                    ai_company_summary TEXT,
                    ai_flags TEXT  -- JSON array
                );
                
                CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
                CREATE INDEX IF NOT EXISTS idx_jobs_relevance_score ON jobs(relevance_score);
                CREATE INDEX IF NOT EXISTS idx_jobs_ai_score ON jobs(ai_score);
                CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_normalized);
                CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_job_url ON jobs(job_url_canonical);
                
                CREATE TABLE IF NOT EXISTS runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    jobs_collected INTEGER DEFAULT 0,
                    jobs_new INTEGER DEFAULT 0,
                    jobs_updated INTEGER DEFAULT 0,
                    jobs_filtered INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    sources TEXT,
                    criteria TEXT  -- JSON
                );
                
                CREATE TABLE IF NOT EXISTS job_sources (
                    job_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_url TEXT,
                    seen_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, source),
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );
            """)

            # Best-effort additive migrations for existing DBs
            try:
                cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
                if "relevance_score" not in cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN relevance_score REAL")
                if "relevance_reasons" not in cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN relevance_reasons TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_relevance_score ON jobs(relevance_score)")
            except Exception:
                # Don't brick local dev if migrations fail
                pass

            conn.commit()

    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def start_run(self, criteria_json: str = "") -> int:
        """Start a new scrape run and return its ID."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO runs (started_at, criteria) VALUES (?, ?)",
                (now_utc_iso(), criteria_json)
            )
            conn.commit()
            return cursor.lastrowid or 0

    def finish_run(self, run_id: int, stats: RunStats) -> None:
        """Finish a scrape run with statistics."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                UPDATE runs SET
                    finished_at = ?,
                    jobs_collected = ?,
                    jobs_new = ?,
                    jobs_updated = ?,
                    jobs_filtered = ?,
                    errors = ?,
                    sources = ?
                WHERE run_id = ?
            """, (
                now_utc_iso(),
                stats.jobs_collected,
                stats.jobs_new,
                stats.jobs_updated,
                stats.jobs_filtered,
                stats.errors,
                stats.sources,
                run_id,
            ))
            conn.commit()

    def upsert_job(self, job: NormalizedJob) -> Tuple[bool, bool]:
        """
        Insert or update a job.
        
        Returns:
            (is_new, was_updated) tuple
        """
        now = now_utc_iso()

        with self._lock:
            conn = self._get_conn()

            # Check if job exists
            cursor = conn.execute(
                "SELECT job_id, first_seen_at FROM jobs WHERE job_id = ?",
                (job.job_id,)
            )
            existing = cursor.fetchone()

            # Prepare data
            employment_types_json = json.dumps([et.value for et in job.employment_types])
            emails_json = json.dumps(job.emails)
            other_urls_json = json.dumps(job.other_urls)
            tags_json = json.dumps(job.tags)
            raw_data_json = json.dumps(job.raw_data) if job.raw_data else None
            
            # AI fields
            ai_employment_types_json = json.dumps(job.ai_employment_types) if job.ai_employment_types else None
            ai_flags_json = json.dumps(job.ai_flags) if job.ai_flags else None

            posted_at = job.posted_at.isoformat() if job.posted_at else None
            expires_at = job.expires_at.isoformat() if job.expires_at else None

            if existing:
                # Update existing job
                first_seen = existing["first_seen_at"]
                conn.execute("""
                    UPDATE jobs SET
                        provider_id = ?,
                        source = ?,
                        source_url = ?,
                        title = ?,
                        title_normalized = ?,
                        company = ?,
                        company_normalized = ?,
                        location_raw = ?,
                        country = ?,
                        city = ?,
                        remote_type = ?,
                        employment_types = ?,
                        salary_min = ?,
                        salary_max = ?,
                        salary_currency = ?,
                        job_url = ?,
                        job_url_canonical = ?,
                        apply_url = ?,
                        description_text = ?,
                        emails = ?,
                        company_website = ?,
                        linkedin_url = ?,
                        twitter_url = ?,
                        facebook_url = ?,
                        instagram_url = ?,
                        youtube_url = ?,
                        other_urls = ?,
                        tags = ?,
                        founder = ?,
                        posted_at = COALESCE(?, posted_at),
                        expires_at = ?,
                        last_seen_at = ?,
                        raw_data = ?,
                        relevance_score = COALESCE(?, relevance_score),
                        relevance_reasons = COALESCE(?, relevance_reasons),
                        ai_score = COALESCE(?, ai_score),
                        ai_reasons = COALESCE(?, ai_reasons),
                        ai_remote_type = COALESCE(?, ai_remote_type),
                        ai_employment_types = COALESCE(?, ai_employment_types),
                        ai_seniority = COALESCE(?, ai_seniority),
                        ai_confidence = COALESCE(?, ai_confidence),
                        ai_summary = COALESCE(?, ai_summary),
                        ai_requirements = COALESCE(?, ai_requirements),
                        ai_tech_stack = COALESCE(?, ai_tech_stack),
                        ai_company_domain = COALESCE(?, ai_company_domain),
                        ai_company_summary = COALESCE(?, ai_company_summary),
                        ai_flags = COALESCE(?, ai_flags)
                    WHERE job_id = ?
                """, (
                    job.provider_id, job.source, job.source_url,
                    job.title, job.title_normalized,
                    job.company, job.company_normalized,
                    job.location_raw, job.country, job.city,
                    job.remote_type.value,
                    employment_types_json,
                    job.salary_min, job.salary_max, job.salary_currency,
                    job.job_url, job.job_url_canonical, job.apply_url,
                    job.description_text,
                    emails_json,
                    job.company_website,
                    job.linkedin_url, job.twitter_url, job.facebook_url,
                    job.instagram_url, job.youtube_url,
                    other_urls_json,
                    tags_json,
                    job.founder,
                    posted_at, expires_at, now,
                    raw_data_json,
                    job.relevance_score,
                    job.relevance_reasons,
                    job.ai_score, job.ai_reasons, job.ai_remote_type,
                    ai_employment_types_json, job.ai_seniority, job.ai_confidence,
                    job.ai_summary, job.ai_requirements, job.ai_tech_stack,
                    job.ai_company_domain, job.ai_company_summary, ai_flags_json,
                    job.job_id,
                ))
                conn.commit()
                return False, True
            else:
                # Insert new job
                conn.execute("""
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
                        raw_data,
                        relevance_score, relevance_reasons,
                        ai_score, ai_reasons, ai_remote_type, ai_employment_types,
                        ai_seniority, ai_confidence, ai_summary, ai_requirements,
                        ai_tech_stack, ai_company_domain, ai_company_summary, ai_flags
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?
                    )
                """, (
                    job.job_id, job.provider_id, job.source, job.source_url,
                    job.title, job.title_normalized, job.company, job.company_normalized,
                    job.location_raw, job.country, job.city,
                    job.remote_type.value,
                    employment_types_json,
                    job.salary_min, job.salary_max, job.salary_currency,
                    job.job_url, job.job_url_canonical, job.apply_url,
                    job.description_text,
                    emails_json,
                    job.company_website,
                    job.linkedin_url, job.twitter_url, job.facebook_url,
                    job.instagram_url, job.youtube_url,
                    other_urls_json,
                    tags_json,
                    job.founder,
                    posted_at, expires_at, now, now,
                    raw_data_json,
                    job.relevance_score,
                    job.relevance_reasons,
                    job.ai_score, job.ai_reasons, job.ai_remote_type,
                    ai_employment_types_json, job.ai_seniority, job.ai_confidence,
                    job.ai_summary, job.ai_requirements, job.ai_tech_stack,
                    job.ai_company_domain, job.ai_company_summary, ai_flags_json,
                ))
                conn.commit()
                return True, False

    def upsert_jobs(self, jobs: List[NormalizedJob]) -> Tuple[int, int]:
        """
        Upsert multiple jobs.
        
        Returns:
            (new_count, updated_count) tuple
        """
        new_count = 0
        updated_count = 0

        for job in jobs:
            is_new, was_updated = self.upsert_job(job)
            if is_new:
                new_count += 1
            elif was_updated:
                updated_count += 1

        return new_count, updated_count

    def add_job_source(self, job_id: str, source: str, source_url: str) -> None:
        """Record that a job was seen from a particular source."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO job_sources (job_id, source, source_url, seen_at) VALUES (?, ?, ?, ?)",
                (job_id, source, source_url, now_utc_iso())
            )
            conn.commit()

    def get_recent_jobs(self, days: int = 30) -> List[Dict]:
        """Get jobs seen in the last N days."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM jobs
                WHERE date(last_seen_at) >= date('now', ?)
                ORDER BY posted_at DESC, first_seen_at DESC
            """, (f"-{days} days",))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_jobs(self) -> List[Dict]:
        """Get all jobs."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM jobs
                ORDER BY posted_at DESC, first_seen_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_job_count(self) -> int:
        """Get total job count."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            result = cursor.fetchone()
            return result[0] if result else 0

    def has_job(self, job_id: str) -> bool:
        """Check if a job exists in the database."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT 1 FROM jobs WHERE job_id = ?",
                (job_id,)
            )
            return cursor.fetchone() is not None

    def export_to_csv(self, path: str, days: Optional[int] = None) -> int:
        """
        Export jobs to CSV file.
        
        Returns number of rows exported.
        """
        if days:
            jobs = self.get_recent_jobs(days)
        else:
            jobs = self.get_all_jobs()

        if not jobs:
            return 0

        df = pd.DataFrame(jobs)

        # Clean up JSON columns
        json_cols = ["employment_types", "emails", "other_urls", "tags", "ai_employment_types", "ai_flags"]
        for col in json_cols:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: "; ".join(json.loads(x)) if x else ""
                )

        # Remove internal columns
        drop_cols = ["raw_data", "title_normalized", "company_normalized"]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        df.to_csv(path, index=False, encoding="utf-8")
        return len(df)

    def export_to_excel(self, path: str, days: Optional[int] = None) -> int:
        """
        Export jobs to Excel file.
        
        Returns number of rows exported.
        """
        if days:
            jobs = self.get_recent_jobs(days)
        else:
            jobs = self.get_all_jobs()

        if not jobs:
            return 0

        df = pd.DataFrame(jobs)

        # Clean up JSON columns
        json_cols = ["employment_types", "emails", "other_urls", "tags", "ai_employment_types", "ai_flags"]
        for col in json_cols:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: "; ".join(json.loads(x)) if x else ""
                )

        # Remove internal columns
        drop_cols = ["raw_data", "title_normalized", "company_normalized"]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        df.to_excel(path, index=False)
        return len(df)

