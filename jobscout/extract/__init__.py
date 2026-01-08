"""
Extraction utilities for JobScout.

Provides:
- JSON-LD extraction and parsing (tolerant of malformed data)
- HTML content extraction
- Email and social link extraction
- Enrichment utilities
"""

from jobscout.extract.jsonld import extract_job_postings_from_html, parse_job_posting
from jobscout.extract.html import strip_html, extract_text_structured
from jobscout.extract.enrich import (
    extract_emails,
    extract_social_links,
    guess_founder,
    enrich_job,
)

__all__ = [
    "extract_job_postings_from_html",
    "parse_job_posting",
    "strip_html",
    "extract_text_structured",
    "extract_emails",
    "extract_social_links",
    "guess_founder",
    "enrich_job",
]

