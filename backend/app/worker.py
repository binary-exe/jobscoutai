"""
Background worker for running scrape jobs.

Integrates with the core jobscout scraper.
"""

import asyncio
import os
import time
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
            except Exception:
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
        # Cost control: default off (can be enabled via settings for trusted/admin runs).
        enrich_company_pages=bool(getattr(settings, "scrape_enrich_company_pages", False)),
        max_enrichment_pages=int(getattr(settings, "scrape_max_enrichment_pages", 2)),
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

    # Set SerpAPI key and max_pages for serpapi_google_jobs provider (if enabled)
    if getattr(settings, "serpapi_api_key", None):
        os.environ["JOBSCOUT_SERPAPI_API_KEY"] = settings.serpapi_api_key
    provider_env_map = {
        "themuse_api_key": "JOBSCOUT_THEMUSE_API_KEY",
        "careerjet_api_key": "JOBSCOUT_CAREERJET_API_KEY",
        "careerjet_locale_code": "JOBSCOUT_CAREERJET_LOCALE_CODE",
        "careerjet_user_ip": "JOBSCOUT_CAREERJET_USER_IP",
        "careerjet_user_agent": "JOBSCOUT_CAREERJET_USER_AGENT",
        "adzuna_app_id": "JOBSCOUT_ADZUNA_APP_ID",
        "adzuna_app_key": "JOBSCOUT_ADZUNA_APP_KEY",
        "adzuna_country": "JOBSCOUT_ADZUNA_COUNTRY",
        "findwork_api_key": "JOBSCOUT_FINDWORK_API_KEY",
        "usajobs_api_key": "JOBSCOUT_USAJOBS_API_KEY",
        "usajobs_user_agent": "JOBSCOUT_USAJOBS_USER_AGENT",
        "reed_api_key": "JOBSCOUT_REED_API_KEY",
        "okjob_api_key": "JOBSCOUT_OKJOB_API_KEY",
        "okjob_api_url": "JOBSCOUT_OKJOB_API_URL",
        "jobs2careers_api_key": "JOBSCOUT_JOBS2CAREERS_API_KEY",
        "jobs2careers_api_url": "JOBSCOUT_JOBS2CAREERS_API_URL",
        "whatjobs_api_key": "JOBSCOUT_WHATJOBS_API_KEY",
        "whatjobs_api_url": "JOBSCOUT_WHATJOBS_API_URL",
        "juju_api_key": "JOBSCOUT_JUJU_API_KEY",
        "juju_api_url": "JOBSCOUT_JUJU_API_URL",
        "arbeitsamt_client_id": "JOBSCOUT_ARBEITSAMT_CLIENT_ID",
        "arbeitsamt_client_secret": "JOBSCOUT_ARBEITSAMT_CLIENT_SECRET",
        "arbeitsamt_token_url": "JOBSCOUT_ARBEITSAMT_TOKEN_URL",
        "arbeitsamt_api_url": "JOBSCOUT_ARBEITSAMT_API_URL",
        "open_skills_api_url": "JOBSCOUT_OPEN_SKILLS_API_URL",
    }
    for attr_name, env_name in provider_env_map.items():
        value = getattr(settings, attr_name, None)
        if value is not None and str(value).strip():
            os.environ[env_name] = str(value)
    enabled_set = {p.lower().strip() for p in (settings.enabled_providers or []) if isinstance(p, str)}
    if "serpapi_google_jobs" in enabled_set:
        os.environ["JOBSCOUT_SERPAPI_MAX_PAGES"] = str(getattr(settings, "serpapi_max_pages", 1))

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
        new_job_count = await _sync_to_postgres(db_path)
        os.remove(db_path)
        
        # Auto-backfill embeddings for new jobs (for personalized ranking)
        await _backfill_embeddings_for_new_jobs(new_job_count)

    return stats


async def _sync_to_postgres(sqlite_path: str) -> int:
    """
    Sync jobs from SQLite to Postgres.
    
    Returns the number of new jobs inserted.
    """
    import sqlite3
    from backend.app.core.database import db
    from backend.app.storage.postgres import upsert_job_from_dict

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM jobs").fetchall()
    conn.close()

    new_count = 0
    async with db.connection() as pg_conn:
        for row in rows:
            is_new, _ = await upsert_job_from_dict(pg_conn, dict(row))
            if is_new:
                new_count += 1
    
    return new_count


async def _backfill_embeddings_for_new_jobs(new_job_count: int) -> None:
    """
    Backfill embeddings for newly added jobs after a scrape run.
    
    This ensures personalized ranking stays up-to-date without manual intervention.
    """
    if new_job_count == 0:
        return
    
    settings = get_settings()
    if not settings.embeddings_enabled:
        return
    
    try:
        from backend.app.services.embeddings import backfill_new_job_embeddings
        
        # Backfill slightly more than new_count to catch any missed jobs
        limit = min(new_job_count + 10, 100)
        updated, skipped = await backfill_new_job_embeddings(limit=limit)
        
        if updated > 0:
            print(f"[Embeddings] Auto-backfilled {updated} job embeddings ({skipped} skipped)")
    except Exception as e:
        # Don't fail the scrape if embedding backfill fails
        print(f"[Embeddings] Auto-backfill failed (non-fatal): {e}")


# Lock to prevent overlapping scheduled scrape ticks.
_scheduled_lock = asyncio.Lock()


async def run_scheduled_scrape():
    """Run scheduled scrape: sequential, rotated, non-AI, with lock."""
    settings = get_settings()
    async with _scheduled_lock:
        await _run_scheduled_scrape_locked(settings)


async def _run_scheduled_scrape_locked(settings):
    """Execute scheduled scrape (caller must hold _scheduled_lock)."""
    async def _run_selected_queries() -> None:
        queries = [
            q.strip()
            for q in (settings.resolved_scheduled_queries or [])
            if isinstance(q, str) and q.strip()
        ]
        if not queries and settings.default_search_query:
            queries = [settings.default_search_query]
        if not queries:
            print("[Scheduler] No scheduled queries configured; skipping")
            return

        per_run = max(1, int(settings.scheduled_queries_per_run or 1))
        max_results = max(1, int(settings.scheduled_scrape_max_results_per_source or 1))
        concurrency = max(1, int(settings.scheduled_scrape_concurrency or 1))

        # Restart-safe rotation: derive the slice from scheduler tick.
        interval_hours = max(1, int(settings.scrape_interval_hours or 1))
        interval_seconds = interval_hours * 3600
        tick = int(time.time() // interval_seconds)
        start_idx = (tick * per_run) % len(queries)
        slice_queries = [queries[(start_idx + i) % len(queries)] for i in range(per_run)]

        print(f"[Scheduler] Starting scheduled scrape for {len(slice_queries)} of {len(queries)} query(ies)")

        try:
            for query in slice_queries:
                # Run sequentially (await, don't enqueue) to avoid stacking.
                run_id = await _run_scheduled_single(
                    query=query,
                    location=settings.default_location,
                    max_results_per_source=max_results,
                    concurrency=concurrency,
                )
                print(f"[Scheduler] Scrape completed: \"{query}\" (run_id={run_id})")
        except Exception as e:
            print(f"[Scheduler] Scrape failed: {e}")

    # Postgres advisory lock to prevent multi-instance double-scheduling.
    if settings.use_sqlite:
        await _run_selected_queries()
        return

    from backend.app.core.database import db

    if not db.pool:
        print("[Scheduler] Database pool unavailable; skipping scheduled run")
        return

    lock_expr = "hashtext('jobscout_scheduled_scrape')::bigint"
    async with db.connection() as advisory_conn:
        acquired = False
        try:
            acquired = bool(
                await advisory_conn.fetchval(
                    f"SELECT pg_try_advisory_lock({lock_expr})"
                )
            )
            if not acquired:
                print("[Scheduler] Another instance holds scheduled lock; skipping")
                return

            await _run_selected_queries()
        except Exception as e:
            print(f"[Scheduler] Advisory lock check failed: {e}")
            return
        finally:
            if acquired:
                try:
                    await advisory_conn.fetchval(
                        f"SELECT pg_advisory_unlock({lock_expr})"
                    )
                except Exception as e:
                    print(f"[Scheduler] Failed to release advisory lock: {e}")


async def _run_scheduled_single(
    query: str,
    location: str,
    max_results_per_source: int,
    concurrency: int,
) -> Optional[int]:
    """Run a single scheduled scrape synchronously; returns run_id (None when use_sqlite)."""
    from backend.app.core.config import get_settings
    from backend.app.core.database import db
    from backend.app.storage.postgres import start_run, finish_run
    import json

    settings = get_settings()
    run_id: Optional[int] = None

    if not settings.use_sqlite and db.pool:
        criteria_dict = {"query": query, "location": location, "use_ai": False}
        async with db.connection() as conn:
            run_id = await start_run(conn, json.dumps(criteria_dict))

    try:
        stats = await trigger_scrape_run(
            query=query,
            location=location,
            use_ai=False,
            max_results_per_source=max_results_per_source,
            concurrency=concurrency,
            run_id=run_id,
        )
        if run_id is not None and db.pool:
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
        print(f"[Worker] Scheduled scrape failed: {e}")
        if run_id is not None and db.pool:
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
                        sources="",
                    )
            except Exception:
                pass

    return run_id
