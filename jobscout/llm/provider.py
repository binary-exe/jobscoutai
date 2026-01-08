"""
LLM provider interface and configuration.

Provides a minimal abstraction for LLM clients with support for
OpenAI and compatible APIs.
"""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class LLMConfig:
    """Configuration for LLM client."""
    
    # API settings
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    
    # Cost controls
    max_tokens: int = 1500
    temperature: float = 0.1
    max_jobs_per_run: int = 100
    max_dedupe_checks: int = 20
    
    # Caching
    use_cache: bool = True
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.environ.get("JOBSCOUT_OPENAI_API_KEY", ""),
            model=os.environ.get("JOBSCOUT_OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.environ.get("JOBSCOUT_OPENAI_BASE_URL"),
            max_jobs_per_run=int(os.environ.get("JOBSCOUT_AI_MAX_JOBS", "100")),
            max_dedupe_checks=int(os.environ.get("JOBSCOUT_AI_MAX_DEDUPE", "20")),
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str = ""
    json_data: Optional[Dict[str, Any]] = None
    tokens_used: int = 0
    cached: bool = False
    error: str = ""
    
    @property
    def ok(self) -> bool:
        return bool(self.content) and not self.error


class LLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a completion from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            json_mode: If True, request JSON output
            
        Returns:
            LLMResponse with content and metadata
        """
        raise NotImplementedError
    
    @abstractmethod
    async def complete_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> List[LLMResponse]:
        """
        Generate completions for multiple prompts.
        
        Args:
            prompts: List of user prompts
            system_prompt: Shared system prompt
            json_mode: If True, request JSON output
            
        Returns:
            List of LLMResponse objects
        """
        raise NotImplementedError
    
    def cache_key(self, prompt: str, system_prompt: Optional[str], step: str) -> str:
        """Generate a cache key for a prompt."""
        key_data = f"{self.config.model}:{system_prompt or ''}:{prompt}:{step}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]


def get_llm_client(config: Optional[LLMConfig] = None) -> Optional["OpenAIClient"]:
    """
    Get an LLM client based on configuration.
    
    Returns None if not configured.
    """
    if config is None:
        config = LLMConfig.from_env()
    
    if not config.is_configured:
        return None
    
    from jobscout.llm.openai_client import OpenAIClient
    return OpenAIClient(config)
