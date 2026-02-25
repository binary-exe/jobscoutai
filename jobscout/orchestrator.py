"""
Main orchestrator for JobScout scraping runs.

Ties together discovery, providers, filtering, deduplication,
enrichment, AI analysis, storage, and export into a single run_scrape() function.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional, Tuple

from jobscout.models import Criteria, NormalizedJob
from jobscout.fetchers.http import HttpFetcher
from jobscout.fetchers.browser import BrowserFetcher
from jobscout.dedupe import DedupeEngine
from jobscout.storage.sqlite import JobDatabase, RunStats
from jobscout.extract.enrich import enrich_job

# Providers
from jobscout.providers.remotive import RemotiveProvider
from jobscout.providers.remoteok import RemoteOKProvider
from jobscout.providers.arbeitnow import ArbeitnowProvider
from jobscout.providers.weworkremotely import WWRRssProvider
from jobscout.providers.greenhouse import GreenhouseProvider
from jobscout.providers.lever import LeverProvider
from jobscout.providers.ashby import AshbyProvider
from jobscout.providers.recruitee import RecruiteeProvider
from jobscout.providers.schemaorg import SchemaOrgProvider
from jobscout.providers.workingnomads import WorkingNomadsProvider
from jobscout.providers.remoteco import RemoteCoProvider
from jobscout.providers.justremote import JustRemoteProvider
from jobscout.providers.wellfound import WellfoundProvider
from jobscout.providers.stackoverflow import StackOverflowProvider
from jobscout.providers.indeed import IndeedProvider
from jobscout.providers.flexjobs import FlexJobsProvider
from jobscout.providers.serpapi_google_jobs import SerpAPIGoogleJobsProvider
from jobscout.providers.jobicy import JobicyProvider
from jobscout.providers.devitjobs_uk import DevITjobsUKProvider
from jobscout.providers.themuse import TheMuseProvider
from jobscout.providers.careerjet import CareerjetProvider
from jobscout.providers.adzuna import AdzunaProvider
from jobscout.providers.findwork import FindworkProvider
from jobscout.providers.usajobs import USAJobsProvider
from jobscout.providers.reed import ReedProvider
from jobscout.providers.okjob import OkJobProvider
from jobscout.providers.jobs2careers import Jobs2CareersProvider
from jobscout.providers.whatjobs import WhatJobsProvider
from jobscout.providers.juju import JujuProvider
from jobscout.providers.arbeitsamt import ArbeitsamtProvider
from jobscout.providers.base import Provider

# Discovery (optional dependency)
try:
    from jobscout.providers.discovery import discover_all, HAS_DDGS
except ImportError:
    HAS_DDGS = False

    def discover_all(criteria: Criteria) -> dict:
        return {
            "lever_sites": [],
            "greenhouse_tokens": [],
            "ashby_slugs": [],
            "recruitee_companies": [],
            "other_urls": [],
        }


async def _collect_from_provider(
    provider: Provider,
    fetcher: HttpFetcher,
    criteria: Criteria,
    log_fn=None,
) -> Tuple[str, List[NormalizedJob], int]:
    """Collect jobs from a single provider, returning (name, jobs, errors)."""
    log = log_fn or (lambda x: None)
    try:
        jobs = await provider.collect(fetcher, criteria)
        errors = provider.stats.errors
        if errors > 0 and provider.stats.error_messages:
            log(f"    {provider.name} errors: {'; '.join(provider.stats.error_messages[:3])}")
        return provider.name, jobs, errors
    except Exception as e:
        error_msg = str(e)[:100] if str(e) else type(e).__name__
        log(f"    {provider.name} failed: {error_msg}")
        return provider.name, [], 1


async def _enrich_jobs(
    jobs: List[NormalizedJob],
    fetcher: HttpFetcher,
    criteria: Criteria,
    max_concurrent: int = 5,
) -> List[NormalizedJob]:
    """Enrich jobs with additional data from their pages."""
    if not criteria.enrich_company_pages:
        return jobs

    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_one(job: NormalizedJob) -> NormalizedJob:
        async with semaphore:
            try:
                return await enrich_job(job, fetcher, max_pages=criteria.max_enrichment_pages)
            except Exception:
                return job

    tasks = [enrich_one(job) for job in jobs]
    return await asyncio.gather(*tasks)


async def _run_ai_pipeline(
    jobs: List[NormalizedJob],
    criteria: Criteria,
    db_path: str,
    ai_config: Optional[dict] = None,
    log_fn=None,
) -> List[NormalizedJob]:
    """
    Run AI analysis pipeline on jobs.
    
    Steps: classify -> company research -> enrich -> rank -> alerts
    """
    if not jobs:
        return jobs
    
    log = log_fn or (lambda x: None)
    
    # Get AI configuration
    config = ai_config or {}
    max_jobs = config.get("max_jobs", 100)
    use_cache = config.get("use_cache", True)
    
    # Try to get LLM client
    try:
        from jobscout.llm.provider import LLMConfig, get_llm_client
        from jobscout.llm.cache import LLMCache
        from jobscout.llm.classify import classify_jobs_batch
        from jobscout.llm.rank import rank_jobs
        from jobscout.llm.enrich_llm import enrich_jobs_batch
        from jobscout.llm.company_agent import analyze_companies_batch
        from jobscout.llm.alerts import check_jobs_batch
    except ImportError as e:
        log(f"  AI modules not available: {e}")
        return jobs
    
    # Create LLM config
    llm_config = LLMConfig.from_env()
    if config.get("model"):
        llm_config.model = config["model"]
    if config.get("max_jobs"):
        llm_config.max_jobs_per_run = config["max_jobs"]
    
    if not llm_config.is_configured:
        log("  AI not configured (set JOBSCOUT_OPENAI_API_KEY)")
        return jobs
    
    client = get_llm_client(llm_config)
    if not client:
        log("  Failed to create LLM client")
        return jobs
    
    # Setup cache
    cache = None
    if use_cache:
        cache = LLMCache(db_path)
    
    processed_jobs = jobs
    
    try:
        # Step 1: Classification
        log(f"  AI: Classifying {min(len(processed_jobs), max_jobs)} jobs...")
        processed_jobs = await classify_jobs_batch(
            processed_jobs, client, cache,
            update_fields=True,
            confidence_threshold=0.7,
            max_jobs=max_jobs,
        )
        
        # Step 2: Company research
        log(f"  AI: Researching companies...")
        processed_jobs = await analyze_companies_batch(
            processed_jobs, client, cache,
            max_jobs=max_jobs,
        )
        
        # Step 3: LLM enrichment (summary, requirements, tech stack)
        log(f"  AI: Extracting job details...")
        processed_jobs = await enrich_jobs_batch(
            processed_jobs, client, cache,
            max_jobs=max_jobs,
        )
        
        # Step 4: Ranking
        log(f"  AI: Ranking jobs...")
        processed_jobs = await rank_jobs(
            processed_jobs, criteria, client, cache,
            batch_size=10,
            max_jobs=max_jobs,
        )
        
        # Step 5: Quality/safety alerts
        log(f"  AI: Checking job quality...")
        processed_jobs = await check_jobs_batch(
            processed_jobs, client, cache,
            use_llm=True,
            max_jobs=max_jobs,
        )
        
        log(f"  AI pipeline complete")
        
    except Exception as e:
        log(f"  AI pipeline error: {e}")
    
    finally:
        if cache:
            cache.close()
    
    return processed_jobs


async def run_scrape(
    criteria: Criteria,
    db_path: str = "jobs.db",
    csv_path: Optional[str] = "jobs.csv",
    xlsx_path: Optional[str] = "jobs.xlsx",
    export_days: Optional[int] = None,
    verbose: bool = False,
    use_ai: bool = False,
    ai_config: Optional[dict] = None,
    enabled_providers: Optional[List[str]] = None,
) -> RunStats:
    """
    Run a complete job scraping session.

    Args:
        criteria: Search criteria and configuration
        db_path: Path to SQLite database
        csv_path: Path to export CSV (None to skip)
        xlsx_path: Path to export Excel (None to skip)
        export_days: Only export jobs from last N days (None for all)
        verbose: Print progress messages
        use_ai: Enable AI-powered analysis (requires OpenAI API key)
        ai_config: Optional AI configuration dict:
            - model: OpenAI model name (default: gpt-4o-mini)
            - max_jobs: Max jobs to process with AI (default: 100)
            - max_dedupe: Max dedupe pairs for LLM arbitration (default: 20)
            - use_cache: Cache LLM responses (default: True)

    Returns:
        RunStats with collection statistics
    """
    def log(msg: str) -> None:
        if verbose:
            print(f"[JobScout] {msg}")

    # Initialize database and start run
    db = JobDatabase(db_path)
    criteria_json = json.dumps(asdict(criteria), default=str)
    run_id = db.start_run(criteria_json)

    stats = RunStats(run_id=run_id, started_at=datetime.utcnow().isoformat())
    sources_used: List[str] = []
    all_jobs: List[NormalizedJob] = []
    total_errors = 0

    # Create fetchers
    cache_dir = os.path.join(os.path.dirname(db_path) or ".", ".jobscout_cache")
    fetcher = HttpFetcher(
        timeout_s=criteria.request_timeout_s,
        cache_dir=cache_dir if criteria.use_cache else None,
        cache_ttl_hours=criteria.cache_ttl_hours,
    )

    browser_fetcher: Optional[BrowserFetcher] = None
    if criteria.use_browser:
        from jobscout.fetchers.browser import BrowserConfig
        browser_fetcher = BrowserFetcher(BrowserConfig(
            headless=True,
            timeout_ms=criteria.browser_timeout_s * 1000,
        ))

    try:
        async with fetcher:
            # Optionally start browser
            if browser_fetcher:
                await browser_fetcher.start()

            # ===================== Discovery (optional) =====================
            discovered = {"lever_sites": [], "greenhouse_tokens": [], "ashby_slugs": [], "recruitee_companies": [], "other_urls": []}
            if criteria.enable_discovery:
                log("Running discovery...")
                if HAS_DDGS:
                    try:
                        discovered = discover_all(criteria)
                        log(f"  Discovered: {len(discovered['lever_sites'])} Lever, "
                            f"{len(discovered['greenhouse_tokens'])} Greenhouse, "
                            f"{len(discovered['ashby_slugs'])} Ashby, "
                            f"{len(discovered['recruitee_companies'])} Recruitee, "
                            f"{len(discovered['other_urls'])} other URLs")
                    except Exception as e:
                        log(f"  Discovery failed: {e}")
                else:
                    log("  Skipping discovery (duckduckgo_search not installed)")
            else:
                log("Skipping discovery (disabled)")

            # ===================== Build Provider List =====================
            providers: List[Provider] = []
            
            # Provider registry mapping names to classes
            provider_registry: dict[str, type] = {
                "remotive": RemotiveProvider,
                "remoteok": RemoteOKProvider,
                "arbeitnow": ArbeitnowProvider,
                "weworkremotely": WWRRssProvider,
                "workingnomads": WorkingNomadsProvider,
                "remoteco": RemoteCoProvider,
                "justremote": JustRemoteProvider,
                "wellfound": WellfoundProvider,
                "stackoverflow": StackOverflowProvider,
                "indeed": IndeedProvider,
                "flexjobs": FlexJobsProvider,
                "serpapi_google_jobs": SerpAPIGoogleJobsProvider,
                "jobicy": JobicyProvider,
                "devitjobs_uk": DevITjobsUKProvider,
                "themuse": TheMuseProvider,
                "careerjet": CareerjetProvider,
                "adzuna": AdzunaProvider,
                "findwork": FindworkProvider,
                "usajobs": USAJobsProvider,
                "reed": ReedProvider,
                "okjob": OkJobProvider,
                "jobs2careers": Jobs2CareersProvider,
                "whatjobs": WhatJobsProvider,
                "juju": JujuProvider,
                "arbeitsamt": ArbeitsamtProvider,
            }

            # Filter providers if allowlist is specified
            if enabled_providers:
                enabled_set = {p.lower().strip() for p in enabled_providers}
                log(f"Provider allowlist: {', '.join(sorted(enabled_set))}")
                for name, provider_class in provider_registry.items():
                    if name in enabled_set:
                        providers.append(provider_class())
            else:
                # Use all built-in providers if no allowlist
                for provider_class in provider_registry.values():
                    providers.append(provider_class())

            # Discovered ATS providers
            if discovered["lever_sites"]:
                providers.append(LeverProvider(discovered["lever_sites"]))
            if discovered["greenhouse_tokens"]:
                providers.append(GreenhouseProvider(discovered["greenhouse_tokens"]))
            if discovered["ashby_slugs"]:
                providers.append(AshbyProvider(discovered["ashby_slugs"]))
            if discovered["recruitee_companies"]:
                providers.append(RecruiteeProvider(discovered["recruitee_companies"]))

            # Schema.org provider for other discovered URLs
            if discovered["other_urls"]:
                schema_provider = SchemaOrgProvider(
                    urls=discovered["other_urls"],
                    use_browser=criteria.use_browser,
                )
                if browser_fetcher:
                    schema_provider.set_browser_fetcher(browser_fetcher)
                providers.append(schema_provider)

            log(f"Collecting from {len(providers)} providers...")

            # ===================== Collect Jobs =====================
            # Run providers with bounded concurrency
            semaphore = asyncio.Semaphore(criteria.concurrency)

            async def collect_bounded(p: Provider) -> Tuple[str, List[NormalizedJob], int]:
                async with semaphore:
                    return await _collect_from_provider(p, fetcher, criteria, log_fn=log)

            tasks = [collect_bounded(p) for p in providers]
            results = await asyncio.gather(*tasks)

            for name, jobs, errors in results:
                sources_used.append(name)
                all_jobs.extend(jobs)
                total_errors += errors
                log(f"  {name}: {len(jobs)} jobs, {errors} errors")

            stats.jobs_collected = len(all_jobs)
            log(f"Total collected: {len(all_jobs)} jobs")

            # ===================== Filter Jobs =====================
            log("Filtering jobs...")
            filtered_jobs = [j for j in all_jobs if j.matches_criteria(criteria)]
            stats.jobs_filtered = len(all_jobs) - len(filtered_jobs)
            log(f"  After filtering: {len(filtered_jobs)} jobs ({stats.jobs_filtered} filtered out)")

            # ===================== Deduplicate Jobs =====================
            log("Deduplicating jobs...")
            dedupe_engine = DedupeEngine()
            dedupe_result = dedupe_engine.dedupe(filtered_jobs, track_uncertain=use_ai)
            unique_jobs = dedupe_result.unique_jobs
            log(f"  After dedupe: {len(unique_jobs)} jobs ({dedupe_result.duplicates_removed} duplicates removed)")
            
            # LLM dedupe arbitration for uncertain pairs
            if use_ai and dedupe_result.uncertain_pairs:
                log(f"  {len(dedupe_result.uncertain_pairs)} uncertain pairs found for LLM arbitration")
                try:
                    from jobscout.llm.provider import LLMConfig, get_llm_client
                    from jobscout.llm.cache import LLMCache
                    from jobscout.llm.dedupe_arbiter import arbitrate_uncertain_pairs, merge_duplicates
                    
                    llm_config = LLMConfig.from_env()
                    max_dedupe = (ai_config or {}).get("max_dedupe", 20)
                    
                    if llm_config.is_configured:
                        client = get_llm_client(llm_config)
                        cache = LLMCache(db_path)
                        
                        pairs_to_check = dedupe_result.uncertain_pairs[:max_dedupe]
                        decisions = await arbitrate_uncertain_pairs(pairs_to_check, client, cache)
                        
                        # Merge confirmed duplicates
                        before_count = len(unique_jobs)
                        unique_jobs = merge_duplicates(decisions, unique_jobs)
                        merged = before_count - len(unique_jobs)
                        
                        cache.close()
                        log(f"  LLM arbitration: {merged} additional duplicates merged")
                except Exception as e:
                    log(f"  LLM dedupe arbitration failed: {e}")

            # ===================== Enrich Jobs (HTTP) =====================
            if criteria.enrich_company_pages and unique_jobs:
                log(f"Enriching {len(unique_jobs)} jobs...")
                unique_jobs = await _enrich_jobs(
                    unique_jobs,
                    fetcher,
                    criteria,
                    max_concurrent=min(5, criteria.concurrency),
                )
                log("  Enrichment complete")

            # ===================== AI Pipeline =====================
            if use_ai and unique_jobs:
                log("Running AI analysis pipeline...")
                unique_jobs = await _run_ai_pipeline(
                    unique_jobs,
                    criteria,
                    db_path,
                    ai_config=ai_config,
                    log_fn=log,
                )

            # ===================== Deterministic Scoring (non-AI) =====================
            if unique_jobs:
                try:
                    from jobscout.scoring import apply_relevance_scoring
                    apply_relevance_scoring(unique_jobs, criteria)
                except Exception as e:
                    log(f"Relevance scoring failed (non-fatal): {e}")

            # ===================== Save to Database =====================
            log("Saving to database...")
            new_count, updated_count = db.upsert_jobs(unique_jobs)
            stats.jobs_new = new_count
            stats.jobs_updated = updated_count
            log(f"  {new_count} new, {updated_count} updated")

    finally:
        # Clean up browser
        if browser_fetcher:
            await browser_fetcher.close()

    # ===================== Export =====================
    if csv_path:
        log(f"Exporting to CSV: {csv_path}")
        count = db.export_to_csv(csv_path, days=export_days)
        log(f"  Exported {count} jobs")

    if xlsx_path:
        log(f"Exporting to Excel: {xlsx_path}")
        count = db.export_to_excel(xlsx_path, days=export_days)
        log(f"  Exported {count} jobs")

    # Finalize run stats
    stats.errors = total_errors
    stats.sources = ", ".join(sources_used)
    # Get job count before closing DB
    total_jobs = db.get_job_count() if db._conn else None
    db.finish_run(run_id, stats)
    db.close()

    log(f"Run complete. Total jobs in DB: {total_jobs if total_jobs is not None else 'N/A'}")

    return stats
