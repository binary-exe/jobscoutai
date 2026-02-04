"""
Supabase Auth helpers.

We validate user identity by calling Supabase Auth's /auth/v1/user endpoint with the
provided JWT (Authorization: Bearer ...). This avoids adding JWT verification deps
and keeps the backend stateless.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import httpx
from fastapi import Depends, Header, HTTPException

from backend.app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AuthUser:
    user_id: UUID
    email: Optional[str] = None


async def _supabase_get_user(settings: Settings, token: str) -> AuthUser:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase auth not configured")

    url = settings.supabase_url.rstrip("/") + "/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.supabase_anon_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    data = resp.json()
    try:
        user_id = UUID(data.get("id"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    email = data.get("email")
    return AuthUser(user_id=user_id, email=email)


def _parse_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization: Bearer token required")
    return await _supabase_get_user(settings, token)


async def get_optional_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    settings: Settings = Depends(get_settings),
) -> Optional[AuthUser]:
    token = _parse_bearer(authorization)
    if not token:
        return None
    return await _supabase_get_user(settings, token)

