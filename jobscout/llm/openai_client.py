"""
OpenAI API client implementation.

Supports OpenAI API and compatible endpoints (Azure, local, etc.)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from jobscout.llm.provider import LLMClient, LLMConfig, LLMResponse


class OpenAIClient(LLMClient):
    """OpenAI API client with async support."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client = None
        self._async_client = None
    
    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                import openai
                kwargs = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url
                self._client = openai.OpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client
    
    def _get_async_client(self):
        """Lazy-load the async OpenAI client."""
        if self._async_client is None:
            try:
                import openai
                kwargs = {"api_key": self.config.api_key}
                if self.config.base_url:
                    kwargs["base_url"] = self.config.base_url
                self._async_client = openai.AsyncOpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._async_client
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate a completion using OpenAI API."""
        try:
            client = self._get_async_client()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            kwargs: Dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = await client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Try to parse JSON if requested
            json_data = None
            if json_mode and content:
                try:
                    json_data = json.loads(content)
                except json.JSONDecodeError:
                    pass
            
            return LLMResponse(
                content=content,
                json_data=json_data,
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            return LLMResponse(error=str(e))
    
    async def complete_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> List[LLMResponse]:
        """Generate completions for multiple prompts concurrently."""
        # Use bounded concurrency to avoid rate limits
        semaphore = asyncio.Semaphore(5)
        
        async def complete_one(prompt: str) -> LLMResponse:
            async with semaphore:
                return await self.complete(prompt, system_prompt, json_mode)
        
        tasks = [complete_one(p) for p in prompts]
        return await asyncio.gather(*tasks)
