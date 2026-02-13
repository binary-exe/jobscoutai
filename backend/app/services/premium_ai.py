"""
Premium AI features for Apply Workspace.

Design goals:
- Optional (disabled unless configured)
- Quota-gated (per-plan caps in Postgres)
- Cached (avoid repeat spend; keyed by stable hashes)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from backend.app.core.config import Settings


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hash_text(text: str, *, max_len: int = 200_000) -> str:
    """Stable hash for large texts (bounded length)."""
    t = (text or "").strip()
    if len(t) > max_len:
        t = t[:max_len]
    return _sha256_hex(t)


def make_cache_key(
    *,
    user_id: UUID,
    feature: str,
    resume_hash: str,
    job_hash: str,
    template_id: str = "",
    version: str = "v1",
) -> str:
    key = f"{version}:{user_id}:{feature}:{resume_hash}:{job_hash}:{template_id}"
    return _sha256_hex(key)[:40]


@dataclass(frozen=True)
class PremiumAIResult:
    response_json: Dict[str, Any]
    model: str
    tokens_used: int


async def _get_client(settings: Settings, *, max_tokens: int, temperature: float):
    from jobscout.llm.provider import LLMConfig, get_llm_client

    llm_config = LLMConfig(
        api_key=settings.openai_api_key or "",
        model=settings.openai_model,
        max_tokens=max_tokens,
        temperature=temperature,
        use_cache=False,  # caching handled in Postgres for premium features
    )
    client = get_llm_client(llm_config)
    return client


async def generate_interview_coach(
    *,
    settings: Settings,
    resume_text: str,
    job_text: str,
) -> PremiumAIResult:
    """
    Generate structured interview prep: questions + rubric + suggested stories.
    """
    client = await _get_client(
        settings,
        max_tokens=int(getattr(settings, "premium_ai_max_tokens_interview", 1200)),
        temperature=0.2,
    )
    if not client:
        raise RuntimeError("AI not configured (missing OpenAI client)")

    system_prompt = (
        "You are an expert technical recruiter and interview coach. "
        "Be practical, concise, and aligned to the job description. "
        "Return strictly valid JSON."
    )

    prompt = f"""
Create an interview prep pack tailored to this resume and job description.

RESUME (trimmed):
{resume_text[:12000]}

JOB DESCRIPTION (trimmed):
{job_text[:12000]}

Return JSON with this shape:
{{
  "questions": [
    {{
      "type": "behavioral|technical|system_design|role_fit",
      "question": "...",
      "why_they_ask": "...",
      "what_good_looks_like": ["...", "..."],
      "red_flags": ["...", "..."],
      "difficulty": "easy|medium|hard"
    }}
  ],
  "rubric": [
    {{
      "dimension": "communication|technical_depth|ownership|impact|role_alignment",
      "how_to_score": "..."
    }}
  ],
  "suggested_stories": [
    {{
      "story_prompt": "Tell me about a time when ...",
      "STAR_outline": {{"S":"...","T":"...","A":"...","R":"..."}}
    }}
  ],
  "next_steps": ["...", "..."]
}}

Constraints:
- 8–12 questions total (balanced mix)
- Keep each field short (1–3 sentences max)
"""

    resp = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    if not resp.ok or not resp.json_data:
        raise RuntimeError(resp.error or "AI generation failed")

    return PremiumAIResult(
        response_json=resp.json_data,
        model=settings.openai_model,
        tokens_used=int(resp.tokens_used or 0),
    )


async def generate_template(
    *,
    settings: Settings,
    template_id: str,
    resume_text: str,
    job_text: str,
    tone: str = "professional",
) -> PremiumAIResult:
    """
    Generate a premium template (cover letter, follow-up, etc.).
    """
    client = await _get_client(
        settings,
        max_tokens=int(getattr(settings, "premium_ai_max_tokens_template", 900)),
        temperature=0.4,
    )
    if not client:
        raise RuntimeError("AI not configured (missing OpenAI client)")

    template_id_norm = (template_id or "").strip().lower()
    tone_norm = (tone or "professional").strip().lower()

    system_prompt = (
        "You are a helpful career coach. "
        "Write high-signal, non-generic templates that can be copy/pasted. "
        "Return strictly valid JSON."
    )

    prompt = f"""
Generate a {template_id_norm} template in a {tone_norm} tone.

RESUME (trimmed):
{resume_text[:12000]}

JOB DESCRIPTION (trimmed):
{job_text[:12000]}

Return JSON with this shape:
{{
  "template_id": "{template_id_norm}",
  "tone": "{tone_norm}",
  "content": "..."
}}

Constraints:
- Content must be 150–350 words (unless template_id is 'follow_up_email', then 80–180 words).
- Avoid fluff and generic claims.
- Use placeholders ONLY where user-specific info is missing, like {{Hiring Manager}}.
"""

    resp = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    if not resp.ok or not resp.json_data:
        raise RuntimeError(resp.error or "AI generation failed")

    return PremiumAIResult(
        response_json=resp.json_data,
        model=settings.openai_model,
        tokens_used=int(resp.tokens_used or 0),
    )

