"""
Command-line interface for JobScout.

Usage:
    python -m jobscout "AI automation engineer" --location Europe --remote-only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Optional

from jobscout.models import Criteria, split_keywords


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="jobscout",
        description="High-accuracy job aggregator for remote opportunities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search
  python -m jobscout "AI automation engineer"

  # With location and filters
  python -m jobscout "workflow automation" --location Europe --remote-only

  # With keyword filters
  python -m jobscout "integration engineer" --must-include "n8n,Zapier" --must-exclude "senior,lead"

  # Custom output paths
  python -m jobscout "RPA developer" --db ./data/jobs.db --csv ./output/jobs.csv --xlsx ./output/jobs.xlsx

  # With browser for JS-rendered pages (requires playwright)
  python -m jobscout "automation engineer" --browser

  # With AI-powered analysis (requires JOBSCOUT_OPENAI_API_KEY env var)
  python -m jobscout "automation engineer" --ai -v

  # AI with custom model and limits
  python -m jobscout "automation engineer" --ai --ai-model gpt-4o --ai-max-jobs 50
""",
    )

    # Required
    parser.add_argument(
        "query",
        help="Primary search query (e.g., 'AI automation engineer')",
    )

    # Location
    parser.add_argument(
        "--location", "-l",
        default="",
        help="Location filter (e.g., 'Europe', 'Netherlands', 'Remote')",
    )

    # Keyword filters
    parser.add_argument(
        "--must-include", "-i",
        default="",
        help="Keywords that MUST appear (comma-separated, AND logic)",
    )
    parser.add_argument(
        "--any-include", "-a",
        default="",
        help="At least ONE of these keywords must appear (comma-separated, OR logic)",
    )
    parser.add_argument(
        "--must-exclude", "-e",
        default="",
        help="Keywords to exclude (comma-separated)",
    )

    # Remote/job type filters
    parser.add_argument(
        "--remote-only", "-r",
        action="store_true",
        default=True,
        help="Only include remote jobs (default: True)",
    )
    parser.add_argument(
        "--no-remote-only",
        action="store_false",
        dest="remote_only",
        help="Include non-remote jobs",
    )
    parser.add_argument(
        "--strict-remote",
        action="store_true",
        default=False,
        help="Strictly require 'remote' classification (excludes unknown)",
    )

    # Employment type filters
    parser.add_argument(
        "--no-contract",
        action="store_true",
        help="Exclude contract positions",
    )
    parser.add_argument(
        "--no-freelance",
        action="store_true",
        help="Exclude freelance positions",
    )
    parser.add_argument(
        "--no-fulltime",
        action="store_true",
        help="Exclude full-time positions",
    )
    parser.add_argument(
        "--include-internship",
        action="store_true",
        help="Include internship positions",
    )

    # Output paths
    parser.add_argument(
        "--db",
        default="jobs.db",
        help="SQLite database path (default: jobs.db)",
    )
    parser.add_argument(
        "--csv",
        default="jobs.csv",
        help="CSV export path (default: jobs.csv, use 'none' to skip)",
    )
    parser.add_argument(
        "--xlsx",
        default="jobs.xlsx",
        help="Excel export path (default: jobs.xlsx, use 'none' to skip)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only export jobs from last N days (default: all)",
    )

    # Behavior
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Use browser for JS-rendered pages (requires playwright)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable HTTP response caching",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip enrichment (faster but less data)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Enable ATS discovery (DuckDuckGo-based). Off by default for reliability/cost control.",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=12,
        help="Max concurrent requests (default: 12)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=200,
        help="Max results per source (default: 200)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request timeout in seconds (default: 20)",
    )

    # AI features
    ai_group = parser.add_argument_group("AI features (requires JOBSCOUT_OPENAI_API_KEY)")
    ai_group.add_argument(
        "--ai",
        action="store_true",
        help="Enable AI-powered analysis (classification, ranking, enrichment, alerts)",
    )
    ai_group.add_argument(
        "--ai-model",
        default="gpt-4o-mini",
        help="OpenAI model to use (default: gpt-4o-mini)",
    )
    ai_group.add_argument(
        "--ai-max-jobs",
        type=int,
        default=100,
        help="Max jobs to process with AI (default: 100, for cost control)",
    )
    ai_group.add_argument(
        "--ai-max-dedupe",
        type=int,
        default=20,
        help="Max uncertain pairs for LLM dedupe arbitration (default: 20)",
    )
    ai_group.add_argument(
        "--no-ai-cache",
        action="store_true",
        help="Disable LLM response caching",
    )

    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print progress messages",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except errors",
    )

    return parser.parse_args(argv)


def build_criteria(args: argparse.Namespace) -> Criteria:
    """Build Criteria object from parsed arguments."""
    return Criteria(
        primary_query=args.query,
        must_include=split_keywords(args.must_include),
        any_include=split_keywords(args.any_include),
        must_exclude=split_keywords(args.must_exclude),
        location=args.location,
        remote_only=args.remote_only,
        strict_remote=args.strict_remote,
        include_contract=not args.no_contract,
        include_freelance=not args.no_freelance,
        include_full_time=not args.no_fulltime,
        include_internship=args.include_internship,
        max_results_per_source=args.max_results,
        enrich_company_pages=not args.no_enrich,
        request_timeout_s=args.timeout,
        concurrency=args.concurrency,
        use_browser=args.browser,
        use_cache=not args.no_cache,
        enable_discovery=bool(getattr(args, "discover", False)),
    )


async def async_main(args: argparse.Namespace) -> int:
    """Async entry point."""
    from jobscout.orchestrator import run_scrape

    criteria = build_criteria(args)

    csv_path = None if args.csv.lower() == "none" else args.csv
    xlsx_path = None if args.xlsx.lower() == "none" else args.xlsx

    verbose = args.verbose and not args.quiet

    # Build AI config
    ai_config = None
    if args.ai:
        ai_config = {
            "model": args.ai_model,
            "max_jobs": args.ai_max_jobs,
            "max_dedupe": args.ai_max_dedupe,
            "use_cache": not args.no_ai_cache,
        }

    if not args.quiet:
        print(f"JobScout - Searching for: {criteria.primary_query}")
        if criteria.location:
            print(f"  Location: {criteria.location}")
        if criteria.must_include:
            print(f"  Must include: {', '.join(criteria.must_include)}")
        if criteria.must_exclude:
            print(f"  Excluding: {', '.join(criteria.must_exclude)}")
        if args.ai:
            print(f"  AI enabled: {args.ai_model} (max {args.ai_max_jobs} jobs)")
        print()

    try:
        stats = await run_scrape(
            criteria=criteria,
            db_path=args.db,
            csv_path=csv_path,
            xlsx_path=xlsx_path,
            export_days=args.days,
            verbose=verbose,
            use_ai=args.ai,
            ai_config=ai_config,
        )

        if not args.quiet:
            print()
            print("=" * 50)
            print("Run Summary")
            print("=" * 50)
            print(f"  Jobs collected: {stats.jobs_collected}")
            print(f"  Jobs filtered:  {stats.jobs_filtered}")
            print(f"  Jobs new:       {stats.jobs_new}")
            print(f"  Jobs updated:   {stats.jobs_updated}")
            print(f"  Errors:         {stats.errors}")
            print(f"  Sources:        {stats.sources}")
            print()
            print("Output files:")
            print(f"  Database: {args.db}")
            if csv_path:
                print(f"  CSV:      {csv_path}")
            if xlsx_path:
                print(f"  Excel:    {xlsx_path}")

        return 0

    except KeyboardInterrupt:
        if not args.quiet:
            print("\nInterrupted by user")
        return 130

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    args = parse_args(argv)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
