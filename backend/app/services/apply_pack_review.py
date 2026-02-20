"""
Premium-only Apply Pack reviewer loop.

Design goals:
- Optional + disabled by default (cost control)
- Uses a stronger reviewer model (default: gpt-4.1) to approve or provide structured feedback
- Revises with the default (cheaper) model using reviewer instructions
- Strict iteration + timeout + token guardrails
- Cached in Postgres (ai_generation_cache) to avoid repeat spend
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from backend.app.core.config import Settings
from backend.app.services import premium_ai
from backend.app.storage import apply_storage


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_paid_user(user: Optional[Dict[str, Any]]) -> bool:
    return apply_storage.is_paid_user(user)


async def _get_client(*, api_key: str, model: str, max_tokens: int, temperature: float):
    from jobscout.llm.provider import LLMConfig, get_llm_client

    llm_config = LLMConfig(
        api_key=api_key or "",
        model=model,
        max_tokens=int(max_tokens),
        temperature=float(temperature),
        use_cache=False,  # caching handled via Postgres for this feature
    )
    return get_llm_client(llm_config)


def _trim_text(s: str, max_chars: int) -> str:
    t = (s or "").strip()
    return t[:max_chars]


def _bullets_to_text(bullets: Any, max_items: int = 6) -> str:
    if not isinstance(bullets, list):
        return ""
    out = []
    for b in bullets[:max_items]:
        if isinstance(b, dict):
            out.append(f"- {str(b.get('text') or '').strip()}")
        else:
            out.append(f"- {str(b).strip()}")
    return "\n".join([x for x in out if x and x != "-"])


async def review_and_refine_apply_pack(
    *,
    conn,
    settings: Settings,
    user_id: UUID,
    user_row: Optional[Dict[str, Any]],
    resume_hash: str,
    job_hash: str,
    pack_hash: str,
    resume_text: str,
    job_text: str,
    job_title: Optional[str],
    company_name: Optional[str],
    generator_model: str,
    pack_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns refined pack_data. On any failure, returns the original pack_data.
    """
    if not getattr(settings, "apply_pack_review_enabled", False):
        return pack_data
    if not settings.openai_api_key:
        return pack_data
    if not _is_paid_user(user_row):
        return pack_data

    review_model = str(getattr(settings, "apply_pack_review_model", "gpt-4.1-mini") or "gpt-4.1-mini")
    max_iters = int(getattr(settings, "apply_pack_review_max_iters", 2) or 2)
    max_iters = max(1, min(2, max_iters))  # hard safety cap (forced to 2)

    timeout_s = int(getattr(settings, "apply_pack_review_timeout_s", 20) or 20)
    max_tokens_review = int(getattr(settings, "apply_pack_review_max_tokens_review", 900) or 900)
    max_tokens_revise = int(getattr(settings, "apply_pack_review_max_tokens_revise", 1400) or 1400)

    cache_key = premium_ai.make_cache_key(
        user_id=user_id,
        feature="apply_pack_review",
        resume_hash=resume_hash,
        job_hash=job_hash,
        template_id=f"{generator_model}:{review_model}:{max_iters}",
        version="v1",
    )
    cached = await apply_storage.get_ai_generation_cache(conn, cache_key)
    if cached and cached.get("response_json"):
        resp = cached.get("response_json") or {}
        if isinstance(resp, dict) and isinstance(resp.get("pack_data"), dict):
            return resp["pack_data"]

    reviewer = await _get_client(
        api_key=settings.openai_api_key,
        model=review_model,
        max_tokens=max_tokens_review,
        temperature=0.1,
    )
    reviser = await _get_client(
        api_key=settings.openai_api_key,
        model=generator_model,
        max_tokens=max_tokens_revise,
        temperature=0.2,
    )
    if not reviewer or not reviser:
        return pack_data

    system_prompt = (
        "You are a meticulous resume and cover-letter reviewer. "
        "Focus on: grammar, spelling, punctuation, formatting consistency, "
        "indentation, awkward phrasing, missing placeholders, and obvious mismatches to the job. "
        "Be strict but practical. Return strictly valid JSON."
    )

    tokens_used_total = 0
    current = dict(pack_data or {})
    last_review: Dict[str, Any] = {}
    iter_count = 0
    review_used = False

    for _i in range(max_iters):
        prompt = f"""
Review this Apply Pack draft and decide if it is approved.

CONTEXT:
- Job title: {job_title or 'N/A'}
- Company: {company_name or 'N/A'}

RESUME (trimmed):
{_trim_text(resume_text, 6000)}

JOB DESCRIPTION (trimmed):
{_trim_text(job_text, 6000)}

DRAFT SUMMARY:
{(current.get('tailored_summary') or '').strip()}

DRAFT BULLETS:
{_bullets_to_text(current.get('tailored_bullets'))}

DRAFT COVER LETTER (no greeting/sign-off):
{(current.get('cover_note') or '').strip()}

Return JSON with this exact shape:
{{
  "approved": true,
  "issues": [
    {{
      "field": "tailored_summary|tailored_bullets|cover_note",
      "severity": "major|minor",
      "issue": "...",
      "suggestion": "..."
    }}
  ],
  "revision_instructions": {{
    "tailored_summary": "...",
    "tailored_bullets": "...",
    "cover_note": "..."
  }}
}}

Rules:
- If approved=true, issues must be an empty list and revision_instructions must be an empty object.
- revision_instructions should be concise instructions for the generator model (not the user).
"""
        try:
            resp = await asyncio.wait_for(
                reviewer.complete(prompt, system_prompt=system_prompt, json_mode=True),
                timeout=timeout_s,
            )
        except Exception:
            break

        tokens_used_total += int(getattr(resp, "tokens_used", 0) or 0)
        review_used = True
        review_json = resp.json_data if (resp and resp.json_data and isinstance(resp.json_data, dict)) else None
        if not review_json:
            # Can't parse reviewer output: stop to avoid runaway spend.
            break

        last_review = review_json
        iter_count += 1
        approved = bool(review_json.get("approved"))
        if approved:
            break

        instructions = review_json.get("revision_instructions") or {}
        if not isinstance(instructions, dict):
            instructions = {}

        # Revise only failing fields (best-effort)
        if instructions.get("tailored_summary"):
            current["tailored_summary"] = await _revise_text_field(
                reviser,
                timeout_s=timeout_s,
                field_name="professional summary",
                current_text=str(current.get("tailored_summary") or ""),
                instructions=str(instructions.get("tailored_summary") or ""),
                output_constraints="Return ONLY the revised 2-3 sentence summary. No quotes, no bullets.",
            )

        if instructions.get("cover_note"):
            current["cover_note"] = await _revise_text_field(
                reviser,
                timeout_s=timeout_s,
                field_name="cover letter",
                current_text=str(current.get("cover_note") or ""),
                instructions=str(instructions.get("cover_note") or ""),
                output_constraints=(
                    "Return ONLY the revised cover letter body as 3-5 short paragraphs. "
                    "Do NOT include greeting (Dear ...) or sign-off (Sincerely, ...)."
                ),
            )

        if instructions.get("tailored_bullets"):
            revised_bullets = await _revise_bullets(
                reviser,
                timeout_s=timeout_s,
                current_bullets=current.get("tailored_bullets"),
                instructions=str(instructions.get("tailored_bullets") or ""),
            )
            if revised_bullets is not None:
                current["tailored_bullets"] = revised_bullets

    # Cache best-effort
    try:
        expires_at = _now_utc() + timedelta(days=30)
        request_hash = premium_ai.hash_text(f"{resume_hash}:{job_hash}:{pack_hash}:{generator_model}:{review_model}")
        await apply_storage.upsert_ai_generation_cache(
            conn,
            cache_key=cache_key,
            user_id=user_id,
            feature="apply_pack_review",
            model=review_model,
            request_hash=request_hash,
            request_json={"pack_hash": pack_hash, "generator_model": generator_model},
            response_json={
                "approved": bool(last_review.get("approved")) if isinstance(last_review, dict) else False,
                "iterations": iter_count,
                "pack_data": current,
                "review": last_review,
            },
            tokens_used=tokens_used_total,
            expires_at=expires_at,
        )
    except Exception:
        pass

    current["_review_used"] = review_used
    return current


async def _revise_text_field(
    client,
    *,
    timeout_s: int,
    field_name: str,
    current_text: str,
    instructions: str,
    output_constraints: str,
) -> str:
    system_prompt = (
        "You are an expert editor. Apply the reviewer instructions precisely, "
        "fix grammar/spelling/punctuation, and keep formatting clean."
    )
    prompt = f"""
Revise the following {field_name}.

CURRENT:
{(current_text or '').strip()}

REVIEWER INSTRUCTIONS:
{instructions.strip()}

{output_constraints}
"""
    try:
        resp = await asyncio.wait_for(client.complete(prompt, system_prompt=system_prompt), timeout=timeout_s)
        if resp and resp.ok:
            return (resp.content or "").strip()
    except Exception:
        pass
    return (current_text or "").strip()


async def _revise_bullets(
    client,
    *,
    timeout_s: int,
    current_bullets: Any,
    instructions: str,
) -> Optional[list[Dict[str, Any]]]:
    bullets_text = _bullets_to_text(current_bullets, max_items=6)
    if not bullets_text:
        return None

    system_prompt = (
        "You are an expert resume bullet editor. Fix grammar/typos, keep metrics, "
        "ensure parallel structure, and follow reviewer instructions. Return valid JSON."
    )
    prompt = f"""
Revise these resume bullets.

CURRENT:
{bullets_text}

REVIEWER INSTRUCTIONS:
{instructions.strip()}

Return a JSON object with this exact shape:
{{
  "bullets": [
    {{"text": "...", "match_score": 0}}
  ]
}}

Rules:
- 3-6 bullets
- Keep existing numbers/metrics unless reviewer explicitly says to change them.
- match_score must be 0-100 integer.
"""
    try:
        resp = await asyncio.wait_for(
            client.complete(prompt, system_prompt=system_prompt, json_mode=True),
            timeout=timeout_s,
        )
        data = resp.json_data if (resp and resp.json_data and isinstance(resp.json_data, dict)) else None
        if not data:
            return None
        bullets = data.get("bullets")
        if not isinstance(bullets, list):
            return None
        out: list[Dict[str, Any]] = []
        for b in bullets[:6]:
            if not isinstance(b, dict):
                continue
            text = str(b.get("text") or "").strip()
            if not text:
                continue
            try:
                ms = int(b.get("match_score", 70))
            except Exception:
                ms = 70
            out.append({"text": text, "match_score": max(0, min(100, ms))})
        return out[:5]
    except Exception:
        return None

