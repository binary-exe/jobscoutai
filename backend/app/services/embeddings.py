"""
Embeddings service (OpenAI embeddings API) for personalization.

Uses httpx directly to avoid adding extra dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Dict, List, Optional

import httpx

from backend.app.core.config import get_settings


@dataclass(frozen=True)
class EmbeddingResult:
    ok: bool
    embedding: Optional[List[float]] = None
    error: Optional[str] = None
    model: Optional[str] = None


def hash_text_for_embedding(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_pgvector_literal(embedding: List[float]) -> str:
    """
    Convert a python list[float] to pgvector literal: '[0.1,0.2,...]'.
    This avoids relying on asyncpg having a pgvector codec installed.
    """
    # Keep reasonably compact; pgvector accepts standard float formatting.
    return "[" + ",".join(f"{float(x):.8f}" for x in embedding) + "]"


def build_job_embedding_text(job: Dict[str, Any]) -> str:
    """
    Build a compact representation of a job for semantic similarity.
    Keep stable ordering to maximize cache hits.
    """
    parts: List[str] = []
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    location = (job.get("location_raw") or "").strip()
    remote_type = (job.get("remote_type") or "").strip()
    tags = job.get("tags") or []
    desc = (job.get("description_text") or "").strip()

    if title:
        parts.append(f"Title: {title}")
    if company:
        parts.append(f"Company: {company}")
    if location:
        parts.append(f"Location: {location}")
    if remote_type:
        parts.append(f"RemoteType: {remote_type}")
    if tags:
        try:
            parts.append("Tags: " + ", ".join([str(t) for t in tags][:30]))
        except Exception:
            pass

    # Cap description to keep costs bounded and avoid huge payloads
    if desc:
        parts.append("Description:\n" + desc[:6000])

    return "\n".join(parts).strip()


def build_profile_embedding_text(profile: Dict[str, Any], primary_resume_text: str = "") -> str:
    parts: List[str] = []
    headline = (profile.get("headline") or "").strip()
    location = (profile.get("location") or "").strip()
    desired_roles = profile.get("desired_roles") or []
    skills = profile.get("skills") or []
    interests = profile.get("interests") or []

    if headline:
        parts.append(f"Headline: {headline}")
    if location:
        parts.append(f"Location: {location}")
    if desired_roles:
        parts.append("DesiredRoles: " + ", ".join([str(x) for x in desired_roles][:20]))
    if skills:
        parts.append("Skills: " + ", ".join([str(x) for x in skills][:50]))
    if interests:
        parts.append("Interests: " + ", ".join([str(x) for x in interests][:30]))
    if primary_resume_text:
        parts.append("Resume:\n" + primary_resume_text.strip()[:8000])

    return "\n".join(parts).strip()


async def embed_text(text: str) -> EmbeddingResult:
    settings = get_settings()
    if not settings.openai_api_key:
        return EmbeddingResult(ok=False, error="OpenAI API key not configured")

    # Hard cap
    text = (text or "").strip()
    if not text:
        return EmbeddingResult(ok=False, error="Empty text")

    payload = {
        "model": settings.openai_embedding_model,
        "input": text[:12000],
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post("https://api.openai.com/v1/embeddings", json=payload, headers=headers)
    except Exception as e:
        return EmbeddingResult(ok=False, error=f"Embedding request failed: {e}")

    if resp.status_code != 200:
        return EmbeddingResult(ok=False, error=f"OpenAI embeddings error {resp.status_code}: {resp.text}")

    data = resp.json()
    emb = None
    try:
        emb = data["data"][0]["embedding"]
    except Exception:
        emb = None

    if not isinstance(emb, list):
        return EmbeddingResult(ok=False, error="Invalid embedding response")

    return EmbeddingResult(ok=True, embedding=[float(x) for x in emb], model=settings.openai_embedding_model)


async def backfill_new_job_embeddings(limit: int = 50) -> tuple[int, int]:
    """
    Backfill embeddings for recently added jobs that don't have embeddings.
    
    Called automatically after each scrape run to ensure new jobs get embeddings.
    
    Returns (updated_count, skipped_count).
    """
    settings = get_settings()
    
    # Skip if embeddings aren't enabled
    if not settings.embeddings_enabled:
        return 0, 0
    
    if not settings.openai_api_key:
        return 0, 0
    
    # Import here to avoid circular imports
    from backend.app.core.database import db
    
    updated = 0
    skipped = 0
    
    try:
        async with db.connection() as conn:
            # Check if embedding column exists (pgvector migration applied)
            try:
                rows = await conn.fetch(
                    """
                    SELECT job_id, title, company, location_raw, remote_type, tags, description_text,
                           embedding, job_embedding_hash
                    FROM jobs
                    WHERE embedding IS NULL
                       OR job_embedding_hash IS NULL
                    ORDER BY first_seen_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            except Exception as e:
                # Embedding columns don't exist - pgvector migration not applied
                print(f"[Embeddings] Skipping backfill - columns not available: {e}")
                return 0, 0
            
            for row in rows:
                job = dict(row)
                text = build_job_embedding_text(job)
                h = hash_text_for_embedding(text)
                
                # Skip if already embedded with same hash
                if job.get("job_embedding_hash") == h and job.get("embedding") is not None:
                    skipped += 1
                    continue
                
                result = await embed_text(text)
                if not result.ok or not result.embedding:
                    skipped += 1
                    continue
                
                try:
                    await conn.execute(
                        """
                        UPDATE jobs
                        SET embedding = $2::vector, job_embedding_hash = $3
                        WHERE job_id = $1
                        """,
                        job["job_id"],
                        to_pgvector_literal(result.embedding),
                        h,
                    )
                    updated += 1
                except Exception:
                    skipped += 1
    except Exception as e:
        print(f"[Embeddings] Backfill error: {e}")
    
    return updated, skipped

