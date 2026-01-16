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
    max_results_per_source: int = 100,
    concurrency: int = 8,
) -> None:
    """Run scrape in background (internal function)."""
    from backend.app.core.database import db
    from backend.app.storage.postgres import finish_run
    from jobscout.storage.sqlite import RunStats
    
    try:
        stats: RunStats = await trigger_scrape_run(
            query=query,
            location=location,
            use_ai=use_ai,
            max_results_per_source=max_results_per_source,
            concurrency=concurrency,
            run_id=run_id,
        )
        if run_id:
            async with db.connection() as conn:
                await finish_run(
                    conn, 
                    run_id,
                    jobs_collected=stats.jobs_collected,
                    jobs_new=stats.jobs_new,
                    jobs_updated=stats.jobs_updated,
                    jobs_filtered=stats.jobs_filtered,
                    errors=stats.errors,
                    sources=stats.sources or "",
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
    finally:
        # Release in-flight slot (best-effort). Import inside function to avoid import-time cycles.
        if run_id is not None:
            try:
                from backend.app.api.scrape import mark_run_finished
                await mark_run_finished(run_id)
            except Exception:
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
    asyncio.create_task(
        _run_scrape_background(
            query=query,
            location=location,
            use_ai=use_ai,
            run_id=run_id,
            max_results_per_source=max_results_per_source,
            concurrency=concurrency,
        )
    )
    
    return run_id


async def trigger_scrape_run(
    query: str,
    location: str = "Remote",
    use_ai: bool = False,
    max_results_per_source: int = 100,
    concurrency: int = 8,
    run_id: Optional[int] = None,
):
    """
    Trigger a scrape run using the core jobscout orchestrator.

    Returns RunStats from the core scraper.
    """
    settings = get_settings()

    # Import here to avoid circular imports
    from jobscout.models import Criteria
    from jobscout.orchestrator import run_scrape
    from jobscout.storage.sqlite import RunStats

    criteria = Criteria(
        primary_query=query,
        location=location,
        remote_only=True,
        max_results_per_source=max_results_per_source,
        enrich_company_pages=True,
        concurrency=concurrency,
    )

    # Determine storage path
    if settings.use_sqlite:
        db_path = settings.sqlite_path
    else:
        # For Postgres, we still use SQLite as a staging DB and then sync to Postgres.
        # Use a per-run path to avoid collisions when multiple scrapes overlap.
        suffix = run_id if run_id is not None else "adhoc"
        db_path = f"temp_scrape_{suffix}.db"

    ai_config = None
    if use_ai and settings.ai_enabled and settings.openai_api_key:
        os.environ["JOBSCOUT_OPENAI_API_KEY"] = settings.openai_api_key
        ai_config = {
            "model": settings.openai_model,
            "max_jobs": settings.ai_max_jobs,
        }

    stats: RunStats = await run_scrape(
        criteria=criteria,
        db_path=db_path,
        csv_path=None,
        xlsx_path=None,
        verbose=True,
        use_ai=use_ai and settings.ai_enabled,
        ai_config=ai_config,
        enabled_providers=settings.enabled_providers if settings.enabled_providers else None,
    )

    # If using Postgres, sync from temp SQLite to Postgres
    if not settings.use_sqlite and os.path.exists(db_path):
        await _sync_to_postgres(db_path)
        os.remove(db_path)

    return stats


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
    queries = settings.scheduled_queries or [settings.default_search_query]
    print(f"[Scheduler] Starting scheduled scrape for {len(queries)} query(ies)")

    try:
        for query in queries:
            # Queue as a tracked run (writes to Postgres runs table in production).
            run_id = await enqueue_scrape_run(
                query=query,
                location=settings.default_location,
                use_ai=False,
                max_results_per_source=settings.public_scrape_max_results_per_source,
                concurrency=settings.public_scrape_concurrency,
            )
            print(f"[Scheduler] Scrape queued: \"{query}\" (run_id={run_id})")
    except Exception as e:
        print(f"[Scheduler] Scrape failed: {e}")
