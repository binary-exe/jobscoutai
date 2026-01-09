"""
Public scrape trigger endpoint.

This endpoint is intentionally guarded with lightweight rate limiting and concurrency caps
to prevent abuse and control costs.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.core.config import Settings, get_settings
from backend.app.worker import enqueue_scrape_run

router = APIRouter(prefix="/scrape", tags=["scrape"])

# In-memory guardrails (best-effort; per-instance)
_in_flight: set[int] = set()
_by_ip: Dict[str, Deque[float]] = defaultdict(deque)
_lock = asyncio.Lock()


class ScrapeRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=120)
    location: Optional[str] = None
    use_ai: bool = False


class ScrapeResponse(BaseModel):
    status: str
    run_id: int
    message: str = ""


def _client_ip(request: Request) -> str:
    # Prefer Fly / proxy headers if present
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("", response_model=ScrapeResponse)
async def scrape_now(
    request: Request,
    body: ScrapeRequest,
    settings: Settings = Depends(get_settings),
):
    """
    Trigger an on-demand scrape for the given query.

    Returns a run_id immediately; the run completes in the background.
    """
    if not settings.public_scrape_enabled:
        raise HTTPException(status_code=404, detail="Public scrape disabled")

    ip = _client_ip(request)
    now = time.time()

    async with _lock:
        # Concurrency cap
        if len(_in_flight) >= max(1, settings.public_scrape_max_concurrent):
            raise HTTPException(status_code=429, detail="Scrape capacity reached. Try again shortly.")

        # Rate limit (per IP)
        window_s = 3600
        q = _by_ip[ip]
        while q and (now - q[0]) > window_s:
            q.popleft()
        if len(q) >= max(1, settings.public_scrape_rate_limit_per_hour):
            raise HTTPException(status_code=429, detail="Rate limit reached. Try again later.")
        q.append(now)

        run_id = await enqueue_scrape_run(
            query=body.query,
            location=body.location or settings.public_scrape_default_location,
            use_ai=body.use_ai and settings.ai_enabled,
            max_results_per_source=settings.public_scrape_max_results_per_source,
            concurrency=settings.public_scrape_concurrency,
        )
        _in_flight.add(run_id)

    return ScrapeResponse(status="queued", run_id=run_id, message="Scrape queued")


async def mark_run_finished(run_id: int) -> None:
    """Called by worker to release in-flight slot."""
    async with _lock:
        _in_flight.discard(run_id)

