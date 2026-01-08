"""
JobScout: High-accuracy job + contract opportunity aggregator.

Uses public APIs, ATS feeds, schema.org JSON-LD extraction, and optional
browser automation for JS-rendered company career pages.
"""

__version__ = "2.0.0"

from jobscout.models import Criteria, NormalizedJob, RemoteType, EmploymentType
from jobscout.orchestrator import run_scrape

__all__ = [
    "Criteria",
    "NormalizedJob",
    "RemoteType",
    "EmploymentType",
    "run_scrape",
]

