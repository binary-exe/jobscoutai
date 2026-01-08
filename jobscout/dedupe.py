"""
Multi-layer deduplication for jobs.

Deduplication strategy:
1. Primary: Provider-specific ID (source + provider_id)
2. Secondary: Canonical job URL
3. Tertiary: Fuzzy match on company + title + location within date window
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from jobscout.models import NormalizedJob


@dataclass
class DedupeResult:
    """Result of deduplication."""
    unique_jobs: List[NormalizedJob]
    duplicates_removed: int
    duplicates_by_provider_id: int
    duplicates_by_url: int
    duplicates_by_fuzzy: int
    uncertain_pairs: List[Tuple["NormalizedJob", "NormalizedJob"]] = field(default_factory=list)


def normalize_for_fuzzy(s: str) -> str:
    """
    Normalize string for fuzzy matching.
    Lowercases, removes punctuation, and normalizes whitespace.
    """
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def title_similarity(t1: str, t2: str) -> float:
    """
    Calculate similarity between two job titles.
    Returns a score between 0 and 1.
    """
    # Normalize
    n1 = normalize_for_fuzzy(t1)
    n2 = normalize_for_fuzzy(t2)

    if n1 == n2:
        return 1.0

    # Token overlap (Jaccard similarity)
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union


def company_similarity(c1: str, c2: str) -> float:
    """
    Calculate similarity between two company names.
    Returns a score between 0 and 1.
    """
    n1 = normalize_for_fuzzy(c1)
    n2 = normalize_for_fuzzy(c2)

    if n1 == n2:
        return 1.0

    # Check if one contains the other (handles "Company" vs "Company Inc")
    if n1 in n2 or n2 in n1:
        return 0.9

    # Token overlap
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())

    if not tokens1 or not tokens2:
        return 0.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union


def are_likely_duplicates(
    job1: NormalizedJob,
    job2: NormalizedJob,
    date_window_days: int = 30,
    title_threshold: float = 0.8,
    company_threshold: float = 0.7,
) -> bool:
    """
    Check if two jobs are likely duplicates using fuzzy matching.
    """
    # Company similarity
    company_sim = company_similarity(job1.company, job2.company)
    if company_sim < company_threshold:
        return False

    # Title similarity
    title_sim = title_similarity(job1.title, job2.title)
    if title_sim < title_threshold:
        return False

    # Location check (loose - just check if same general area)
    loc1 = normalize_for_fuzzy(job1.location_raw)
    loc2 = normalize_for_fuzzy(job2.location_raw)
    # If both have locations, they should have some overlap
    if loc1 and loc2:
        loc_tokens1 = set(loc1.split())
        loc_tokens2 = set(loc2.split())
        if not (loc_tokens1 & loc_tokens2):
            # Different locations - probably not duplicates
            return False

    # Date window check
    if job1.posted_at and job2.posted_at:
        date_diff = abs((job1.posted_at - job2.posted_at).days)
        if date_diff > date_window_days:
            return False

    return True


class DedupeEngine:
    """
    Engine for deduplicating jobs using multiple strategies.
    """

    def __init__(
        self,
        date_window_days: int = 30,
        title_threshold: float = 0.8,
        company_threshold: float = 0.7,
    ):
        self.date_window_days = date_window_days
        self.title_threshold = title_threshold
        self.company_threshold = company_threshold

        # Indexes for deduplication
        self._provider_ids: Dict[str, NormalizedJob] = {}  # source:provider_id -> job
        self._urls: Dict[str, NormalizedJob] = {}  # canonical URL -> job
        self._company_title_index: Dict[str, List[NormalizedJob]] = {}  # company_key -> jobs

    def clear(self) -> None:
        """Clear all indexes."""
        self._provider_ids.clear()
        self._urls.clear()
        self._company_title_index.clear()

    def _provider_key(self, job: NormalizedJob) -> Optional[str]:
        """Generate provider-specific key if available."""
        if job.source and job.provider_id:
            return f"{job.source}:{job.provider_id}"
        return None

    def _company_key(self, job: NormalizedJob) -> str:
        """Generate company key for fuzzy matching index."""
        # Use first few characters of normalized company name
        company_norm = normalize_for_fuzzy(job.company)
        if len(company_norm) > 3:
            return company_norm[:4]
        return company_norm

    def _check_provider_id_duplicate(self, job: NormalizedJob) -> Optional[NormalizedJob]:
        """Check for duplicate by provider ID."""
        key = self._provider_key(job)
        if key and key in self._provider_ids:
            return self._provider_ids[key]
        return None

    def _check_url_duplicate(self, job: NormalizedJob) -> Optional[NormalizedJob]:
        """Check for duplicate by URL."""
        if job.job_url_canonical and job.job_url_canonical in self._urls:
            return self._urls[job.job_url_canonical]
        if job.apply_url and job.apply_url in self._urls:
            return self._urls[job.apply_url]
        return None

    def _check_fuzzy_duplicate(
        self,
        job: NormalizedJob,
        uncertain_pairs: Optional[List[Tuple[NormalizedJob, NormalizedJob]]] = None,
    ) -> Optional[NormalizedJob]:
        """
        Check for duplicate using fuzzy matching.
        
        If uncertain_pairs is provided, near-threshold pairs are added to it
        for potential LLM arbitration.
        """
        key = self._company_key(job)

        # Get candidate jobs with similar company names
        candidates = self._company_title_index.get(key, [])

        for candidate in candidates:
            # Check with standard thresholds
            if are_likely_duplicates(
                job,
                candidate,
                date_window_days=self.date_window_days,
                title_threshold=self.title_threshold,
                company_threshold=self.company_threshold,
            ):
                return candidate
            
            # Check if it's near-threshold (uncertain)
            if uncertain_pairs is not None:
                # Use lower thresholds to detect uncertain cases
                if are_likely_duplicates(
                    job,
                    candidate,
                    date_window_days=self.date_window_days,
                    title_threshold=self.title_threshold - 0.15,  # More lenient
                    company_threshold=self.company_threshold - 0.15,
                ):
                    uncertain_pairs.append((job, candidate))

        return None

    def _add_to_indexes(self, job: NormalizedJob) -> None:
        """Add a job to all indexes."""
        # Provider ID index
        key = self._provider_key(job)
        if key:
            self._provider_ids[key] = job

        # URL index
        if job.job_url_canonical:
            self._urls[job.job_url_canonical] = job
        if job.apply_url and job.apply_url != job.job_url_canonical:
            self._urls[job.apply_url] = job

        # Fuzzy matching index
        company_key = self._company_key(job)
        if company_key not in self._company_title_index:
            self._company_title_index[company_key] = []
        self._company_title_index[company_key].append(job)

    def dedupe(
        self,
        jobs: List[NormalizedJob],
        existing_jobs: Optional[List[NormalizedJob]] = None,
        track_uncertain: bool = True,
    ) -> DedupeResult:
        """
        Deduplicate a list of jobs.
        
        Args:
            jobs: New jobs to deduplicate
            existing_jobs: Optional list of existing jobs to check against
            track_uncertain: If True, track near-threshold pairs for LLM arbitration
            
        Returns:
            DedupeResult with unique jobs, statistics, and uncertain pairs
        """
        # Reset indexes
        self.clear()

        # Index existing jobs first
        if existing_jobs:
            for job in existing_jobs:
                self._add_to_indexes(job)

        unique: List[NormalizedJob] = []
        by_provider_id = 0
        by_url = 0
        by_fuzzy = 0
        uncertain_pairs: List[Tuple[NormalizedJob, NormalizedJob]] = []

        for job in jobs:
            # Check provider ID
            dup = self._check_provider_id_duplicate(job)
            if dup:
                by_provider_id += 1
                continue

            # Check URL
            dup = self._check_url_duplicate(job)
            if dup:
                by_url += 1
                continue

            # Check fuzzy match (with uncertain tracking)
            dup = self._check_fuzzy_duplicate(
                job,
                uncertain_pairs=uncertain_pairs if track_uncertain else None,
            )
            if dup:
                by_fuzzy += 1
                continue

            # Not a duplicate - add to indexes and results
            self._add_to_indexes(job)
            unique.append(job)

        # Dedupe the uncertain pairs list (avoid duplicate pairs)
        seen_pair_keys: Set[str] = set()
        unique_uncertain: List[Tuple[NormalizedJob, NormalizedJob]] = []
        for pair in uncertain_pairs:
            key = f"{pair[0].job_id}:{pair[1].job_id}"
            rev_key = f"{pair[1].job_id}:{pair[0].job_id}"
            if key not in seen_pair_keys and rev_key not in seen_pair_keys:
                seen_pair_keys.add(key)
                unique_uncertain.append(pair)

        return DedupeResult(
            unique_jobs=unique,
            duplicates_removed=by_provider_id + by_url + by_fuzzy,
            duplicates_by_provider_id=by_provider_id,
            duplicates_by_url=by_url,
            duplicates_by_fuzzy=by_fuzzy,
            uncertain_pairs=unique_uncertain,
        )


def dedupe_jobs(
    jobs: List[NormalizedJob],
    existing_jobs: Optional[List[NormalizedJob]] = None,
) -> DedupeResult:
    """
    Convenience function to dedupe jobs with default settings.
    """
    engine = DedupeEngine()
    return engine.dedupe(jobs, existing_jobs)

