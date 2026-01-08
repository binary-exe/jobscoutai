"""
Background worker for running scrape jobs.

Integrates with the core jobscout scraper.
"""

import os
from typing import Optional

from backend.app.core.config import get_settings


async def trigger_scrape_run(
    query: str,
    location: str = "Remote",
    use_ai: bool = False,
) -> Optional[int]:
    """
    Trigger a scrape run using the core jobscout orchestrator.

    Returns the run_id.
    """
    settings = get_settings()

    # Import here to avoid circular imports
    from jobscout.models import Criteria
    from jobscout.orchestrator import run_scrape

    criteria = Criteria(
        primary_query=query,
        location=location,
        remote_only=True,
        max_results_per_source=100,
        enrich_company_pages=True,
        concurrency=8,
    )

    # Determine storage path
    if settings.use_sqlite:
        db_path = settings.sqlite_path
    else:
        # For Postgres, we'll still use SQLite for the run and then sync
        db_path = "temp_scrape.db"

    ai_config = None
    if use_ai and settings.ai_enabled and settings.openai_api_key:
        os.environ["JOBSCOUT_OPENAI_API_KEY"] = settings.openai_api_key
        ai_config = {
            "model": settings.openai_model,
            "max_jobs": settings.ai_max_jobs,
        }

    stats = await run_scrape(
        criteria=criteria,
        db_path=db_path,
        csv_path=None,
        xlsx_path=None,
        verbose=True,
        use_ai=use_ai and settings.ai_enabled,
        ai_config=ai_config,
    )

    # If using Postgres, sync from temp SQLite to Postgres
    if not settings.use_sqlite and os.path.exists(db_path):
        await _sync_to_postgres(db_path)
        os.remove(db_path)

    return stats.run_id if hasattr(stats, 'run_id') else None


async def _sync_to_postgres(sqlite_path: str) -> None:
    """Sync jobs from SQLite to Postgres."""
    import sqlite3
    from backend.app.core.database import db
    from backend.app.storage.postgres import upsert_job_from_dict

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM jobs").fetchall()
    conn.close()

    async with db.connection() as pg_conn:
        for row in rows:
            await upsert_job_from_dict(pg_conn, dict(row))


async def run_scheduled_scrape():
    """Run scheduled scrape with default settings."""
    settings = get_settings()
    print(f"[Scheduler] Starting scheduled scrape: {settings.default_search_query}")

    try:
        await trigger_scrape_run(
            query=settings.default_search_query,
            location=settings.default_location,
            use_ai=settings.ai_enabled,
        )
        print("[Scheduler] Scrape completed successfully")
    except Exception as e:
        print(f"[Scheduler] Scrape failed: {e}")
