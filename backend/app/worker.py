"""
Background worker for running scrape jobs.

Integrates with the core jobscout scraper.
"""

import asyncio
import os
from typing import Optional

from backend.app.core.config import get_settings


async def _run_scrape_background(
    query: str,
    location: str = "Remote",
    use_ai: bool = False,
    run_id: Optional[int] = None,
) -> None:
    """Run scrape in background (internal function)."""
    from backend.app.core.database import db
    from backend.app.storage.postgres import finish_run
    
    try:
        result_run_id = await trigger_scrape_run(query, location, use_ai)
        # If we have a run_id, mark it as finished (use result_run_id stats if available)
        target_run_id = run_id or result_run_id
        if target_run_id:
            async with db.connection() as conn:
                # Get stats from the scrape if available, otherwise use defaults
                await finish_run(
                    conn, 
                    target_run_id,
                    jobs_collected=0,
                    jobs_new=0,
                    jobs_updated=0,
                    jobs_filtered=0,
                    errors=0,
                    sources=""
                )
    except Exception as e:
        print(f"[Worker] Background scrape failed: {e}")
        # Mark run as failed if we have run_id
        if run_id:
            try:
                async with db.connection() as conn:
                    await finish_run(
                        conn, 
                        run_id,
                        jobs_collected=0,
                        jobs_new=0,
                        jobs_updated=0,
                        jobs_filtered=0,
                        errors=1,
                        sources=""
                    )
            except:
                pass


async def enqueue_scrape_run(
    query: str,
    location: str = "Remote",
    use_ai: bool = False,
    max_results_per_source: int = 100,
    concurrency: int = 8,
) -> int:
    """
    Enqueue a scrape run to run in the background.
    
    Returns run_id immediately; scrape runs asynchronously.
    """
    settings = get_settings()
    
    # Create run record first to get run_id
    from backend.app.core.database import db
    from backend.app.storage.postgres import start_run
    import json
    
    criteria_dict = {
        "query": query,
        "location": location,
        "use_ai": use_ai,
    }
    
    async with db.connection() as conn:
        run_id = await start_run(conn, json.dumps(criteria_dict))
    
    # Run scrape in background
    asyncio.create_task(_run_scrape_background(query, location, use_ai, run_id))
    
    return run_id


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
