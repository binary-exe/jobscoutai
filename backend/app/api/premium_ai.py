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

INTERVIEW_COACH_CREDITS = 12
TEMPLATE_CREDITS = 5
INTERVIEW_COACH_CACHE_VERSION = "v3_ai_only"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


_PROVIDER_OUTAGE_MARKERS = (
    "insufficient_quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "billing",
    "credit balance",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "connection",
    "network",
)


def _is_provider_outage_error(message: str) -> bool:
    msg = (message or "").lower()
    return any(marker in msg for marker in _PROVIDER_OUTAGE_MARKERS)


def _map_generation_runtime_error(*, feature_label: str, message: str) -> HTTPException:
    msg = (message or "").lower()

    # Provider-side capacity/billing/rate-limit failures should not be shown as user-plan quota.
    if _is_provider_outage_error(msg):
        return HTTPException(
            status_code=503,
            detail="AI provider is temporarily unavailable. Please try again shortly.",
        )

    invalid_output_markers = ("malformed", "invalid", "empty")
    if any(marker in msg for marker in invalid_output_markers):
        return HTTPException(
            status_code=502,
            detail=f"{feature_label} generation returned an invalid response. Please try again.",
        )

    return HTTPException(
        status_code=502,
        detail=f"{feature_label} generation failed. Please try again.",
    )


def _has_interview_content(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    questions = payload.get("questions")
    if isinstance(questions, list) and len(questions) > 0:
        return True
    recommendations = payload.get("recommendations")
    if isinstance(recommendations, list) and len(recommendations) > 0:
        return True
    study_materials = payload.get("study_materials")
    if isinstance(study_materials, list) and len(study_materials) > 0:
        return True
    return False


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
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

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
            version=INTERVIEW_COACH_CACHE_VERSION,
        )

        cached = await apply_storage.get_ai_generation_cache(conn, cache_key)
        if cached and cached.get("response_json"):
            cached_model = str(cached.get("model") or "")
            cached_payload = cached.get("response_json")
            # Ignore stale/legacy fallback or empty cache entries.
            if not cached_model.startswith("fallback:") and _has_interview_content(cached_payload):
                return {
                    "cached": True,
                    "fallback": False,
                    "cache_key": cache_key,
                    "result": cached_payload,
                }

        has_credits = await apply_storage.has_credit_ledger_entries(conn, user_id)
        use_credits = apply_storage.is_paid_user(user) and has_credits
        if use_credits:
            balance = await apply_storage.get_credit_balance(conn, user_id)
            if balance < INTERVIEW_COACH_CREDITS:
                raise HTTPException(status_code=403, detail="Insufficient credits for interview coach.")
        else:
            quota = await apply_storage.check_user_quota(conn, user_id, "ai_interview_coach")
            if not quota.get("allowed"):
                raise HTTPException(status_code=403, detail="Premium AI quota exceeded or not available on your plan.")

        try:
            result = await premium_ai.generate_interview_coach(
                settings=settings,
                resume_text=payload.resume_text,
                job_text=job_text,
            )
        except RuntimeError as e:
            print(f"Interview coach runtime error: {e}")
            raise _map_generation_runtime_error(
                feature_label="Interview prep",
                message=str(e),
            )
        except Exception:
            raise HTTPException(status_code=502, detail="Interview prep generation failed. Please try again.")

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
        if use_credits:
            await apply_storage.spend_credits(
                conn,
                user_id=user_id,
                amount=INTERVIEW_COACH_CREDITS,
                feature="ai_interview_coach",
                idempotency_key=f"{user_id}:ai_interview_coach:{cache_key}",
                metadata={"cache_key": cache_key},
            )

        return {
            "cached": False,
            "fallback": False,
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
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

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

        has_credits = await apply_storage.has_credit_ledger_entries(conn, user_id)
        use_credits = apply_storage.is_paid_user(user) and has_credits
        if use_credits:
            balance = await apply_storage.get_credit_balance(conn, user_id)
            if balance < TEMPLATE_CREDITS:
                raise HTTPException(status_code=403, detail="Insufficient credits for templates.")
        else:
            quota = await apply_storage.check_user_quota(conn, user_id, "ai_template")
            if not quota.get("allowed"):
                raise HTTPException(status_code=403, detail="Premium AI quota exceeded or not available on your plan.")

        try:
            result = await premium_ai.generate_template(
                settings=settings,
                template_id=template_id,
                resume_text=payload.resume_text,
                job_text=job_text,
                tone=tone,
            )
        except RuntimeError as e:
            print(f"Template runtime error: {e}")
            raise _map_generation_runtime_error(
                feature_label="Template",
                message=str(e),
            )
        except Exception:
            raise HTTPException(status_code=502, detail="Template generation failed. Please try again.")

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
        if use_credits:
            await apply_storage.spend_credits(
                conn,
                user_id=user_id,
                amount=TEMPLATE_CREDITS,
                feature="ai_template",
                idempotency_key=f"{user_id}:ai_template:{cache_key}",
                metadata={"cache_key": cache_key},
            )

        return {
            "cached": False,
            "cache_key": cache_key,
            "tokens_used": result.tokens_used,
            "result": result.response_json,
        }

