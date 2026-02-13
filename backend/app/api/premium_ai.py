"""
Premium AI endpoints (quota-gated + cached).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings
from backend.app.core.database import db
from backend.app.storage import apply_storage
from backend.app.services import premium_ai

# Reuse Apply Workspace auth/user bootstrap
from backend.app.api.apply import require_auth_user  # noqa: E402

router = APIRouter(prefix="/apply/ai", tags=["ai-premium"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class InterviewCoachRequest(BaseModel):
    job_target_id: Optional[UUID] = None
    job_text: Optional[str] = None
    resume_text: str = Field(..., min_length=50, max_length=250_000)


class TemplateRequest(BaseModel):
    template_id: str = Field(..., min_length=2, max_length=64)
    tone: str = Field("professional", min_length=2, max_length=32)
    job_target_id: Optional[UUID] = None
    job_text: Optional[str] = None
    resume_text: str = Field(..., min_length=50, max_length=250_000)


@router.post("/interview-coach")
async def interview_coach(
    payload: InterviewCoachRequest,
    user_id: UUID = Depends(require_auth_user),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.premium_ai_enabled:
        raise HTTPException(status_code=404, detail="Premium AI is disabled")
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="AI not configured")

    async with db.connection() as conn:
        # Resolve job text from job_target if provided
        job_text = (payload.job_text or "").strip()
        job_hash = ""
        if payload.job_target_id:
            jt = await apply_storage.get_job_target(conn, user_id=user_id, job_target_id=payload.job_target_id)
            if not jt:
                raise HTTPException(status_code=404, detail="Job target not found")
            job_text = (jt.get("description_text") or jt.get("job_text") or job_text or "").strip()
            job_hash = str(jt.get("job_hash") or "")

        if not job_text:
            raise HTTPException(status_code=400, detail="job_text is required (or provide job_target_id)")

        resume_hash = premium_ai.hash_text(payload.resume_text)
        if not job_hash:
            job_hash = premium_ai.hash_text(job_text)

        cache_key = premium_ai.make_cache_key(
            user_id=user_id,
            feature="interview_coach",
            resume_hash=resume_hash,
            job_hash=job_hash,
            template_id="",
        )

        cached = await apply_storage.get_ai_generation_cache(conn, cache_key)
        if cached and cached.get("response_json"):
            return {
                "cached": True,
                "cache_key": cache_key,
                "result": cached["response_json"],
            }

        quota = await apply_storage.check_user_quota(conn, user_id, "ai_interview_coach")
        if not quota.get("allowed"):
            raise HTTPException(status_code=403, detail="Premium AI quota exceeded or not available on your plan.")

        result = await premium_ai.generate_interview_coach(
            settings=settings,
            resume_text=payload.resume_text,
            job_text=job_text,
        )

        expires_at = _now_utc() + timedelta(days=30)
        request_hash = premium_ai.hash_text(f"{resume_hash}:{job_hash}")
        await apply_storage.upsert_ai_generation_cache(
            conn,
            cache_key=cache_key,
            user_id=user_id,
            feature="interview_coach",
            model=result.model,
            request_hash=request_hash,
            request_json={"job_target_id": str(payload.job_target_id) if payload.job_target_id else None},
            response_json=result.response_json,
            tokens_used=result.tokens_used,
            expires_at=expires_at,
        )

        await apply_storage.record_usage(conn, user_id, "ai_interview_coach")

        return {
            "cached": False,
            "cache_key": cache_key,
            "tokens_used": result.tokens_used,
            "result": result.response_json,
        }


@router.post("/template")
async def create_template(
    payload: TemplateRequest,
    user_id: UUID = Depends(require_auth_user),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.premium_ai_enabled:
        raise HTTPException(status_code=404, detail="Premium AI is disabled")
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="AI not configured")

    template_id = payload.template_id.strip().lower()
    tone = payload.tone.strip().lower()

    async with db.connection() as conn:
        job_text = (payload.job_text or "").strip()
        job_hash = ""
        if payload.job_target_id:
            jt = await apply_storage.get_job_target(conn, user_id=user_id, job_target_id=payload.job_target_id)
            if not jt:
                raise HTTPException(status_code=404, detail="Job target not found")
            job_text = (jt.get("description_text") or jt.get("job_text") or job_text or "").strip()
            job_hash = str(jt.get("job_hash") or "")

        if not job_text:
            raise HTTPException(status_code=400, detail="job_text is required (or provide job_target_id)")

        resume_hash = premium_ai.hash_text(payload.resume_text)
        if not job_hash:
            job_hash = premium_ai.hash_text(job_text)

        cache_key = premium_ai.make_cache_key(
            user_id=user_id,
            feature="template",
            resume_hash=resume_hash,
            job_hash=job_hash,
            template_id=f"{template_id}:{tone}",
        )

        cached = await apply_storage.get_ai_generation_cache(conn, cache_key)
        if cached and cached.get("response_json"):
            return {
                "cached": True,
                "cache_key": cache_key,
                "result": cached["response_json"],
            }

        quota = await apply_storage.check_user_quota(conn, user_id, "ai_template")
        if not quota.get("allowed"):
            raise HTTPException(status_code=403, detail="Premium AI quota exceeded or not available on your plan.")

        result = await premium_ai.generate_template(
            settings=settings,
            template_id=template_id,
            resume_text=payload.resume_text,
            job_text=job_text,
            tone=tone,
        )

        expires_at = _now_utc() + timedelta(days=30)
        request_hash = premium_ai.hash_text(f"{resume_hash}:{job_hash}:{template_id}:{tone}")
        await apply_storage.upsert_ai_generation_cache(
            conn,
            cache_key=cache_key,
            user_id=user_id,
            feature="template",
            model=result.model,
            request_hash=request_hash,
            request_json={"template_id": template_id, "tone": tone},
            response_json=result.response_json,
            tokens_used=result.tokens_used,
            expires_at=expires_at,
        )

        await apply_storage.record_usage(conn, user_id, "ai_template")

        return {
            "cached": False,
            "cache_key": cache_key,
            "tokens_used": result.tokens_used,
            "result": result.response_json,
        }

