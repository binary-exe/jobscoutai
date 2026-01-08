"""
Base provider interface for job sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

from jobscout.models import NormalizedJob, Criteria

if TYPE_CHECKING:
    from jobscout.fetchers.http import HttpFetcher


@dataclass
class ProviderStats:
    """Statistics for a provider run."""
    collected: int = 0
    filtered: int = 0
    errors: int = 0
    error_messages: List[str] = field(default_factory=list)


class Provider(ABC):
    """
    Base class for job source providers.
    
    Each provider is responsible for:
    - Fetching jobs from its source (API, RSS, scraping)
    - Converting raw data to NormalizedJob objects
    - Basic filtering (the orchestrator does additional filtering)
    """

    name: str = "base"

    def __init__(self):
        self.stats = ProviderStats()

    @abstractmethod
    async def collect(
        self,
        fetcher: "HttpFetcher",
        criteria: Criteria,
    ) -> List[NormalizedJob]:
        """
        Collect jobs from this provider.
        
        Args:
            fetcher: HTTP fetcher for making requests
            criteria: Search criteria
            
        Returns:
            List of NormalizedJob objects
        """
        raise NotImplementedError

    def reset_stats(self) -> None:
        """Reset provider statistics."""
        self.stats = ProviderStats()

    def log_error(self, message: str) -> None:
        """Log an error for this provider."""
        self.stats.errors += 1
        if len(self.stats.error_messages) < 10:
            self.stats.error_messages.append(message)

