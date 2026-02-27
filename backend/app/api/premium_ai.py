"""
Premium AI endpoints (quota-gated + cached).
"""

from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)

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


async def _fetch_kb_context_for_interview(
    user_id: UUID,
    company: str,
    job_target_id: Optional[UUID],
) -> str:
    """
    Best-effort fetch of KB chunks relevant to company notes.
    Returns empty string on any error or when KB disabled.
    """
    settings = get_settings()
    if not settings.kb_enabled or not settings.openai_api_key:
        return ""
    try:
        from backend.app.services.embeddings import embed_text
        from backend.app.storage import kb_storage

        question = f"What did the user note about {company or 'the company'}?"
        emb_result = await embed_text(question)
        if not emb_result.ok or not emb_result.embedding:
            return ""
        async with db.connection() as conn:
            chunks = await kb_storage.fetch_similar_chunks(
                conn,
                user_id=user_id,
                embedding=emb_result.embedding,
                limit=5,
            )
        if not chunks:
            return ""
        parts = []
        for c in chunks[:5]:
            snip = (c.get("snippet") or "").strip()[:500]
            if snip:
                parts.append(snip)
        return "\n\n".join(parts) if parts else ""
    except Exception as e:
        logger.info("KB context fetch skipped: %s", e)
        return ""


def _serialize_prep_for_kb(result: Dict[str, Any]) -> str:
    """Serialize interview prep JSON to indexable text."""
    parts = []
    for q in (result.get("questions") or [])[:12]:
        if isinstance(q, dict) and q.get("question"):
            parts.append(f"Q: {q['question']}")
            if q.get("why_they_ask"):
                parts.append(f"  Why: {q['why_they_ask']}")
            if q.get("suggested_answer_outline"):
                parts.append(f"  Outline: {'; '.join(q['suggested_answer_outline'][:3])}")
    for r in (result.get("recommendations") or [])[:8]:
        if r:
            parts.append(f"Recommendation: {r}")
    for m in (result.get("study_materials") or [])[:8]:
        if isinstance(m, dict) and m.get("topic"):
            parts.append(f"Study: {m['topic']} - {m.get('why_it_matters', '')[:200]}")
    for s in (result.get("next_steps") or [])[:6]:
        if s:
            parts.append(f"Next: {s}")
    gap = result.get("gap_analysis") or {}
    if gap.get("matched"):
        parts.append(f"Matched: {', '.join(gap['matched'][:6])}")
    if gap.get("missing"):
        parts.append(f"Missing: {', '.join(gap['missing'][:6])}")
    return "\n\n".join(parts).strip() or json.dumps(result)[:8000]


async def _index_prep_to_kb_fire_and_forget(
    user_id: UUID,
    job_target_id: UUID,
    company: str,
    role: str,
    prep_text: str,
) -> None:
    """Fire-and-forget index of generated prep into KB. Logs errors, never raises."""
    settings = get_settings()
    if not settings.kb_enabled or not settings.openai_api_key:
        return
    try:
        from backend.app.api.kb import _chunk_text
        from backend.app.services.embeddings import embed_text
        from backend.app.storage import kb_storage

        chunks_raw = _chunk_text(prep_text)
        if not chunks_raw:
            return
        chunks_with_emb = []
        for c in chunks_raw:
            result = await embed_text(c["text"])
            if not result.ok or not result.embedding:
                continue
            chunks_with_emb.append({
                "text": c["text"],
                "chunk_index": c["chunk_index"],
                "embedding": result.embedding,
            })
        if not chunks_with_emb:
            return
        async with db.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1",
                    str(user_id),
                )
                await kb_storage.insert_document_and_chunks(
                    conn,
                    user_id=user_id,
                    source_type="interview_notes",
                    source_table="job_targets",
                    source_id=str(job_target_id),
                    title=f"Interview prep - {company or 'Company'} - {role or 'Role'}",
                    chunks=chunks_with_emb,
                )
        logger.info("Indexed interview prep to KB for job_target %s", job_target_id)
    except Exception as e:
        logger.warning("KB auto-index of prep failed: %s", e)


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
        jt_company = ""
        jt_title = ""
        if payload.job_target_id:
            jt = await apply_storage.get_job_target(conn, user_id=user_id, job_target_id=payload.job_target_id)
            if not jt:
                raise HTTPException(status_code=404, detail="Job target not found")
            job_text = (jt.get("description_text") or jt.get("job_text") or job_text or "").strip()
            job_hash = str(jt.get("job_hash") or "")
            jt_company = (jt.get("company") or "").strip()
            jt_title = (jt.get("title") or "").strip()

        if not job_text:
            raise HTTPException(status_code=400, detail="job_text is required (or provide job_target_id)")

        resume_hash = premium_ai.hash_text(payload.resume_text)
        if not job_hash:
            job_hash = premium_ai.hash_text(job_text)

        # Best-effort KB context for company notes (non-blocking)
        kb_context = ""
        try:
            kb_context = await _fetch_kb_context_for_interview(
                user_id=user_id,
                company=jt_company or "the company",
                job_target_id=payload.job_target_id,
            )
        except Exception:
            pass

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
                    "kb_context_used": None,  # Unknown for cached
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
                kb_context=kb_context,
            )
        except RuntimeError as e:
            logger.warning("Interview coach runtime error: %s", e)
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

        # Fire-and-forget: auto-index prep to KB (non-blocking)
        if payload.job_target_id and result.response_json:
            prep_text = _serialize_prep_for_kb(result.response_json)
            if prep_text:
                asyncio.create_task(
                    _index_prep_to_kb_fire_and_forget(
                        user_id=user_id,
                        job_target_id=payload.job_target_id,
                        company=jt_company,
                        role=jt_title,
                        prep_text=prep_text,
                    )
                )

        return {
            "cached": False,
            "fallback": False,
            "cache_key": cache_key,
            "tokens_used": result.tokens_used,
            "result": result.response_json,
            "kb_context_used": bool(kb_context and kb_context.strip()),
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
            logger.warning("Template runtime error: %s", e)
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

