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
            use_ai=request.use_ai and settings.ai_enabled,
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
