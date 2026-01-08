"""
Storage layer for JobScout.

Provides SQLite-based persistence with:
- Job storage with upserts
- Run tracking
- Export to CSV/Excel
"""

from jobscout.storage.sqlite import JobDatabase, RunStats

__all__ = ["JobDatabase", "RunStats"]

