"""
Simple in-memory rate limiting for Apply Workspace endpoints.

This is a basic implementation suitable for single-instance deployments.
For production multi-instance deployments, use Redis-based rate limiting.
"""

import time
from collections import defaultdict
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window.
    
    Tracks requests per user within a time window.
    """
    
    def __init__(self, requests_per_window: int = 10, window_seconds: int = 60):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    def check(self, user_id: UUID) -> bool:
        """
        Check if request is allowed for user.
        Returns True if allowed, False if rate limited.
        """
        key = str(user_id)
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        self._requests[key] = [
            ts for ts in self._requests[key]
            if ts > window_start
        ]
        
        # Check if under limit
        if len(self._requests[key]) >= self.requests_per_window:
            return False
        
        # Record this request
        self._requests[key].append(now)
        return True
    
    def get_retry_after(self, user_id: UUID) -> Optional[int]:
        """Get seconds until the oldest request expires from the window."""
        key = str(user_id)
        if not self._requests.get(key):
            return None
        
        oldest = min(self._requests[key])
        retry_after = int(self.window_seconds - (time.time() - oldest)) + 1
        return max(1, retry_after)


# Global rate limiters for different endpoints
# Apply pack generation: 10 requests per minute per user
apply_pack_limiter = RateLimiter(requests_per_window=10, window_seconds=60)

# Job capture/import (extension, 1-click saves): 30 per hour per user
# Note: this is in-memory and per-instance. It's still useful as a strict guardrail
# in single-instance setups; for multi-instance, swap to a shared store (e.g. Redis).
job_capture_limiter = RateLimiter(requests_per_window=30, window_seconds=60 * 60)


def check_rate_limit(user_id: UUID, limiter: RateLimiter = apply_pack_limiter) -> None:
    """
    Check rate limit and raise HTTPException if exceeded.
    
    Usage in endpoint:
        from backend.app.core.rate_limit import check_rate_limit, apply_pack_limiter
        
        @router.post("/pack/generate")
        async def generate(..., user_id: UUID = Depends(require_auth_user)):
            check_rate_limit(user_id, apply_pack_limiter)
            ...
    """
    if not limiter.check(user_id):
        retry_after = limiter.get_retry_after(user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)} if retry_after else {},
        )
