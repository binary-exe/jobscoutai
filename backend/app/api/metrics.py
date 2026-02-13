"""
Low-cost product analytics (server-side event capture).

This provides a minimal ingestion endpoint that writes events to Postgres.
It is intentionally simple: no external dependencies, no paid vendors required.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from backend.app.core.auth import AuthUser, get_optional_user
from backend.app.core.database import db

router = APIRouter(prefix="/metrics", tags=["metrics"])


class EventIn(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=120)
    properties: Optional[dict[str, Any]] = None
    distinct_id: Optional[str] = Field(default=None, max_length=200)
    path: Optional[str] = Field(default=None, max_length=500)
    client_ts: Optional[datetime] = None


@router.post("/event", status_code=204)
async def capture_event(
    payload: EventIn,
    request: Request,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """
    Capture a single analytics event.

    - Accepts both authenticated and anonymous users (best-effort).
    - Returns 204 always for frontend "fire-and-forget" behavior.
    """
    name = payload.event_name.strip()
    if not name:
        return Response(status_code=204)

    user_id: Optional[UUID] = user.user_id if user else None
    props_json = json.dumps(payload.properties or {}) if payload.properties is not None else None

    async with db.connection() as conn:
        await conn.execute(
            """
            INSERT INTO analytics_events (client_ts, event_name, user_id, distinct_id, path, properties)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            payload.client_ts,
            name,
            user_id,
            payload.distinct_id,
            payload.path,
            props_json,
        )

    return Response(status_code=204)

