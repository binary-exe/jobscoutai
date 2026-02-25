"""
Admin endpoints for triggering scrapes and viewing stats.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import db

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== Schemas ====================

class StatsResponse(BaseModel):
    """System statistics."""

    total_jobs: int
    jobs_last_24h: int
    jobs_last_7d: int
    sources: dict
    last_run_at: Optional[datetime] = None
    last_run_jobs_new: int = 0


class RunTriggerRequest(BaseModel):
    """Request to trigger a scrape run."""

    query: Optional[str] = None
    location: Optional[str] = None
    use_ai: bool = False


class RunTriggerResponse(BaseModel):
    """Response after triggering a run."""

    status: str
    message: str
    run_id: Optional[int] = None


class EmbeddingsBackfillResponse(BaseModel):
    status: str
    updated: int = 0
    skipped: int = 0
    message: Optional[str] = None


# ==================== Auth ====================

def verify_admin_token(
    authorization: str = Header(None),
    settings: Settings = Depends(get_settings),
):
    """Verify admin token from Authorization header."""
    if not settings.admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = authorization.replace("Bearer ", "")
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    return True


# ==================== Endpoints ====================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(settings: Settings = Depends(get_settings)):
    """
    Get system statistics (public, no auth required).
    """
    if settings.use_sqlite:
        return await _get_stats_sqlite(settings)
    return await _get_stats_postgres()


@router.post("/run", response_model=RunTriggerResponse)
async def trigger_run(
    request: RunTriggerRequest,
    _: bool = Depends(verify_admin_token),
    settings: Settings = Depends(get_settings),
):
    """
    Trigger a scrape run. Requires admin token.
    Returns immediately with run_id; scrape runs in background.
    """
    from backend.app.worker import enqueue_scrape_run

    try:
        run_id = await enqueue_scrape_run(
            query=request.query or settings.default_search_query,
            location=request.location or settings.default_location,
            # Keep admin-triggered scraping non-AI for predictable cost/latency.
            # We keep the request field for backwards compatibility.
            use_ai=False,
        )
        return RunTriggerResponse(
            status="started",
            message=f"Scrape run queued",
            run_id=run_id,
        )
    except Exception as e:
        return RunTriggerResponse(
            status="error",
            message=str(e),
        )


@router.post("/embeddings/backfill", response_model=EmbeddingsBackfillResponse)
async def backfill_embeddings(
    limit: int = 200,
    _: bool = Depends(verify_admin_token),
    settings: Settings = Depends(get_settings),
):
    """
    Backfill missing job embeddings for personalized ranking.

    Requires:
    - JOBSCOUT_EMBEDDINGS_ENABLED=true
    - pgvector migration applied (jobs.embedding, jobs.job_embedding_hash)
    """
    if settings.use_sqlite:
        return EmbeddingsBackfillResponse(status="error", message="Embeddings backfill not supported on SQLite")

    if not settings.embeddings_enabled:
        return EmbeddingsBackfillResponse(status="error", message="Embeddings are disabled (JOBSCOUT_EMBEDDINGS_ENABLED=false)")

    from backend.app.services import embeddings

    updated = 0
    skipped = 0

    async with db.connection() as conn:
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
            # Likely pgvector columns not present
            return EmbeddingsBackfillResponse(status="error", message=f"Embedding columns missing or pgvector not enabled: {e}")

        for row in rows:
            job = dict(row)
            text = embeddings.build_job_embedding_text(job)
            h = embeddings.hash_text_for_embedding(text)

            # Skip if already embedded with same hash
            if job.get("job_embedding_hash") == h and job.get("embedding") is not None:
                skipped += 1
                continue

            result = await embeddings.embed_text(text)
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
                    embeddings.to_pgvector_literal(result.embedding),
                    h,
                )
                updated += 1
            except Exception:
                skipped += 1

    return EmbeddingsBackfillResponse(status="ok", updated=updated, skipped=skipped)


# ==================== SQLite Implementation ====================

async def _get_stats_sqlite(settings) -> StatsResponse:
    """Get stats from SQLite."""
    import sqlite3
    from datetime import timedelta

    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row

    # Total jobs
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    # Jobs last 24h
    since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    jobs_24h = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= ?",
        (since_24h,)
    ).fetchone()[0]

    # Jobs last 7d
    since_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
    jobs_7d = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= ?",
        (since_7d,)
    ).fetchone()[0]

    # Sources
    source_rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM jobs GROUP BY source"
    ).fetchall()
    sources = {row["source"]: row["count"] for row in source_rows}

    # Last run
    last_run = conn.execute(
        "SELECT * FROM runs ORDER BY run_id DESC LIMIT 1"
    ).fetchone()

    conn.close()

    return StatsResponse(
        total_jobs=total_jobs,
        jobs_last_24h=jobs_24h,
        jobs_last_7d=jobs_7d,
        sources=sources,
        last_run_at=last_run["finished_at"] if last_run else None,
        last_run_jobs_new=last_run["jobs_new"] if last_run else 0,
    )


async def _get_stats_postgres() -> StatsResponse:
    """Get stats from Postgres."""
    from datetime import timedelta

    async with db.connection() as conn:
        total_jobs = await conn.fetchval("SELECT COUNT(*) FROM jobs")

        since_24h = datetime.utcnow() - timedelta(hours=24)
        jobs_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= $1",
            since_24h
        )

        since_7d = datetime.utcnow() - timedelta(days=7)
        jobs_7d = await conn.fetchval(
            "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= $1",
            since_7d
        )

        source_rows = await conn.fetch(
            "SELECT source, COUNT(*) as count FROM jobs GROUP BY source"
        )
        sources = {row["source"]: row["count"] for row in source_rows}

        last_run = await conn.fetchrow(
            "SELECT * FROM runs ORDER BY run_id DESC LIMIT 1"
        )

    return StatsResponse(
        total_jobs=total_jobs,
        jobs_last_24h=jobs_24h,
        jobs_last_7d=jobs_7d,
        sources=sources,
        last_run_at=last_run["finished_at"] if last_run else None,
        last_run_jobs_new=last_run["jobs_new"] if last_run else 0,
    )
