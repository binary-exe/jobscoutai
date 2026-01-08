"""
LLM response caching utilities.

Caches LLM responses in SQLite to avoid redundant API calls
and reduce costs on re-runs.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from jobscout.llm.provider import LLMResponse


class LLMCache:
    """
    SQLite-based cache for LLM responses.
    
    Cache keys are based on (job_id, step, prompt_hash) to allow
    granular invalidation and efficient lookups.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize cache with database path.
        
        Args:
            db_path: Path to SQLite database (creates llm_cache table)
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def _init_db(self) -> None:
        """Initialize cache table."""
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    cache_key TEXT PRIMARY KEY,
                    job_id TEXT,
                    step TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    response_content TEXT,
                    response_json TEXT,
                    tokens_used INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    model TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_llm_cache_job 
                ON llm_cache(job_id, step)
            """)
            conn.commit()
    
    def get(
        self,
        cache_key: str,
    ) -> Optional[LLMResponse]:
        """
        Get cached response by key.
        
        Args:
            cache_key: Cache key from LLMClient.cache_key()
            
        Returns:
            LLMResponse if cached, None otherwise
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT response_content, response_json, tokens_used FROM llm_cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            json_data = None
            if row["response_json"]:
                try:
                    json_data = json.loads(row["response_json"])
                except json.JSONDecodeError:
                    pass
            
            return LLMResponse(
                content=row["response_content"] or "",
                json_data=json_data,
                tokens_used=row["tokens_used"] or 0,
                cached=True,
            )
    
    def set(
        self,
        cache_key: str,
        response: LLMResponse,
        job_id: str = "",
        step: str = "",
        prompt_hash: str = "",
        model: str = "",
    ) -> None:
        """
        Cache a response.
        
        Args:
            cache_key: Cache key
            response: LLM response to cache
            job_id: Associated job ID (for lookup/invalidation)
            step: Step name (classify, rank, enrich, etc.)
            prompt_hash: Hash of the prompt
            model: Model used
        """
        if not response.ok:
            return  # Don't cache errors
        
        json_str = json.dumps(response.json_data) if response.json_data else None
        
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO llm_cache 
                (cache_key, job_id, step, prompt_hash, response_content, response_json, tokens_used, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cache_key,
                job_id,
                step,
                prompt_hash,
                response.content,
                json_str,
                response.tokens_used,
                model,
            ))
            conn.commit()
    
    def invalidate_job(self, job_id: str) -> int:
        """
        Invalidate all cached responses for a job.
        
        Returns number of entries deleted.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM llm_cache WHERE job_id = ?",
                (job_id,)
            )
            conn.commit()
            return cursor.rowcount
    
    def invalidate_step(self, step: str) -> int:
        """
        Invalidate all cached responses for a step.
        
        Returns number of entries deleted.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM llm_cache WHERE step = ?",
                (step,)
            )
            conn.commit()
            return cursor.rowcount
    
    def clear(self) -> int:
        """
        Clear entire cache.
        
        Returns number of entries deleted.
        """
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM llm_cache")
            conn.commit()
            return cursor.rowcount
    
    def stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(DISTINCT job_id) as unique_jobs,
                    SUM(tokens_used) as total_tokens
                FROM llm_cache
            """)
            row = cursor.fetchone()
            
            return {
                "total_entries": row["total_entries"] or 0,
                "unique_jobs": row["unique_jobs"] or 0,
                "total_tokens": row["total_tokens"] or 0,
            }
    
    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
