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
import re
from collections import Counter
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


_KEYWORD_STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "any",
    "are",
    "been",
    "both",
    "build",
    "building",
    "backend",
    "frontend",
    "engineer",
    "engineers",
    "senior",
    "junior",
    "position",
    "responsible",
    "responsibilities",
    "required",
    "requirement",
    "requirements",
    "candidate",
    "company",
    "create",
    "created",
    "design",
    "designing",
    "develop",
    "developing",
    "improve",
    "improving",
    "optimize",
    "optimizing",
    "day",
    "each",
    "experience",
    "from",
    "have",
    "help",
    "high",
    "into",
    "just",
    "know",
    "level",
    "like",
    "make",
    "more",
    "need",
    "nice",
    "only",
    "our",
    "over",
    "plus",
    "role",
    "self",
    "should",
    "skills",
    "some",
    "that",
    "their",
    "them",
    "they",
    "this",
    "time",
    "using",
    "very",
    "what",
    "when",
    "where",
    "with",
    "work",
    "your",
}


def _to_string(value: Any, *, max_len: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        s = value.strip()
    else:
        s = str(value).strip()
    if not s:
        return ""
    if len(s) > max_len:
        return s[: max_len - 1].rstrip() + "…"
    return s


def _to_string_list(value: Any, *, max_items: int = 8, max_len: int = 300) -> list[str]:
    if isinstance(value, list):
        source = value
    elif isinstance(value, str) and value.strip():
        source = [value]
    else:
        return []
    out: list[str] = []
    for item in source:
        s = _to_string(item, max_len=max_len)
        if s:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


def _normalize_interview_coach_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    questions: list[Dict[str, Any]] = []
    questions_raw = data.get("questions")
    if isinstance(questions_raw, str) and questions_raw.strip():
        questions_raw = [questions_raw]
    elif isinstance(questions_raw, dict):
        questions_raw = [questions_raw]
    if isinstance(questions_raw, list):
        for raw in questions_raw[:12]:
            if isinstance(raw, dict):
                question_text = _to_string(raw.get("question"), max_len=260)
                question_type = _to_string(raw.get("type"), max_len=40).lower()
                why_they_ask = _to_string(raw.get("why_they_ask"), max_len=320)
                what_good_looks_like = _to_string_list(raw.get("what_good_looks_like"), max_items=5, max_len=220)
                red_flags = _to_string_list(raw.get("red_flags"), max_items=5, max_len=220)
                difficulty = _to_string(raw.get("difficulty"), max_len=20).lower()
                if not question_text:
                    continue
                item: Dict[str, Any] = {"question": question_text}
                if question_type:
                    item["type"] = question_type
                if why_they_ask:
                    item["why_they_ask"] = why_they_ask
                if what_good_looks_like:
                    item["what_good_looks_like"] = what_good_looks_like
                if red_flags:
                    item["red_flags"] = red_flags
                suggested_answer_outline = _to_string_list(raw.get("suggested_answer_outline"), max_items=5, max_len=220)
                study_focus = _to_string_list(raw.get("study_focus"), max_items=5, max_len=120)
                if difficulty:
                    item["difficulty"] = difficulty
                if suggested_answer_outline:
                    item["suggested_answer_outline"] = suggested_answer_outline
                if study_focus:
                    item["study_focus"] = study_focus
                questions.append(item)
            elif isinstance(raw, str) and raw.strip():
                questions.append({"question": _to_string(raw, max_len=260)})

    rubric: list[Dict[str, str]] = []
    rubric_raw = data.get("rubric")
    if isinstance(rubric_raw, str) and rubric_raw.strip():
        rubric_raw = [rubric_raw]
    elif isinstance(rubric_raw, dict):
        rubric_raw = [rubric_raw]
    if isinstance(rubric_raw, list):
        for raw in rubric_raw[:8]:
            if isinstance(raw, dict):
                dimension = _to_string(raw.get("dimension"), max_len=80)
                how_to_score = _to_string(raw.get("how_to_score"), max_len=260)
                if not dimension and not how_to_score:
                    continue
                item: Dict[str, str] = {}
                if dimension:
                    item["dimension"] = dimension
                if how_to_score:
                    item["how_to_score"] = how_to_score
                rubric.append(item)
            elif isinstance(raw, str) and raw.strip():
                rubric.append({"how_to_score": _to_string(raw, max_len=260)})

    suggested_stories: list[Dict[str, Any]] = []
    stories_raw = data.get("suggested_stories")
    if isinstance(stories_raw, str) and stories_raw.strip():
        stories_raw = [stories_raw]
    elif isinstance(stories_raw, dict):
        stories_raw = [stories_raw]
    if isinstance(stories_raw, list):
        for raw in stories_raw[:6]:
            if isinstance(raw, dict):
                story_prompt = _to_string(raw.get("story_prompt"), max_len=260)
                star_outline_raw = raw.get("STAR_outline")
                star_outline: Dict[str, str] = {}
                if isinstance(star_outline_raw, dict):
                    for key in ("S", "T", "A", "R"):
                        val = _to_string(star_outline_raw.get(key), max_len=260)
                        if val:
                            star_outline[key] = val
                item: Dict[str, Any] = {}
                if story_prompt:
                    item["story_prompt"] = story_prompt
                if star_outline:
                    item["STAR_outline"] = star_outline
                if item:
                    suggested_stories.append(item)
            elif isinstance(raw, str) and raw.strip():
                suggested_stories.append({"story_prompt": _to_string(raw, max_len=260)})

    next_steps = _to_string_list(data.get("next_steps"), max_items=8, max_len=220)
    recommendations = _to_string_list(data.get("recommendations"), max_items=8, max_len=220)

    study_materials: list[Dict[str, Any]] = []
    materials_raw = data.get("study_materials")
    if isinstance(materials_raw, dict):
        materials_raw = [materials_raw]
    elif isinstance(materials_raw, str) and materials_raw.strip():
        materials_raw = [{"topic": materials_raw}]
    if isinstance(materials_raw, list):
        for raw in materials_raw[:8]:
            if isinstance(raw, str) and raw.strip():
                study_materials.append({"topic": _to_string(raw, max_len=120)})
                continue
            if not isinstance(raw, dict):
                continue
            topic = _to_string(raw.get("topic"), max_len=120)
            why_it_matters = _to_string(raw.get("why_it_matters"), max_len=240)
            priority = _to_string(raw.get("priority"), max_len=24).lower()
            resources = _to_string_list(raw.get("resources"), max_items=5, max_len=180)
            practice_tasks = _to_string_list(raw.get("practice_tasks"), max_items=5, max_len=180)
            item: Dict[str, Any] = {}
            if topic:
                item["topic"] = topic
            if why_it_matters:
                item["why_it_matters"] = why_it_matters
            if priority:
                item["priority"] = priority
            if resources:
                item["resources"] = resources
            if practice_tasks:
                item["practice_tasks"] = practice_tasks
            if item:
                study_materials.append(item)

    preparation_plan: list[Dict[str, Any]] = []
    plan_raw = data.get("preparation_plan")
    if isinstance(plan_raw, dict):
        plan_raw = [plan_raw]
    if isinstance(plan_raw, list):
        for raw in plan_raw[:8]:
            if not isinstance(raw, dict):
                continue
            label = _to_string(raw.get("label"), max_len=80)
            objective = _to_string(raw.get("objective"), max_len=240)
            actions = _to_string_list(raw.get("actions"), max_items=6, max_len=180)
            item: Dict[str, Any] = {}
            if label:
                item["label"] = label
            if objective:
                item["objective"] = objective
            if actions:
                item["actions"] = actions
            if item:
                preparation_plan.append(item)

    gap_analysis: Dict[str, Any] = {}
    gap_raw = data.get("gap_analysis")
    if isinstance(gap_raw, dict):
        matched = _to_string_list(gap_raw.get("matched"), max_items=12, max_len=80)
        missing = _to_string_list(gap_raw.get("missing"), max_items=12, max_len=80)
        notes = _to_string_list(gap_raw.get("notes"), max_items=6, max_len=180)
        if matched:
            gap_analysis["matched"] = matched
        if missing:
            gap_analysis["missing"] = missing
        if notes:
            gap_analysis["notes"] = notes

    return {
        "questions": questions,
        "rubric": rubric,
        "suggested_stories": suggested_stories,
        "recommendations": recommendations,
        "study_materials": study_materials,
        "preparation_plan": preparation_plan,
        "gap_analysis": gap_analysis,
        "next_steps": next_steps,
    }


def _normalize_template_payload(
    data: Dict[str, Any], *, template_id: str, tone: str, fallback_content: str = ""
) -> Dict[str, Any]:
    template_id_raw = data.get("template_id")
    tone_raw = data.get("tone")
    content_raw = data.get("content")

    template_id_value = (
        _to_string(template_id_raw, max_len=64) if isinstance(template_id_raw, str) else ""
    ) or template_id
    tone_value = (_to_string(tone_raw, max_len=32) if isinstance(tone_raw, str) else "") or tone
    content_value = (
        _to_string(content_raw, max_len=5000) if isinstance(content_raw, str) else ""
    ) or _to_string(fallback_content, max_len=5000)
    return {
        "template_id": template_id_value,
        "tone": tone_value,
        "content": content_value,
    }


def _try_parse_json_object(content: str) -> Optional[Dict[str, Any]]:
    text = (content or "").strip()
    if not text:
        return None

    # Direct parse.
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    # Common markdown fence wrapper.
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if fenced and fenced != text:
        try:
            parsed = json.loads(fenced)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

    # Best-effort object extraction.
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            parsed = json.loads(m.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _extract_focus_terms(text: str, *, max_items: int = 6) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", (text or "").lower())
    tokens = [
        tok.strip(".,;:!?()[]{}")
        for tok in raw_tokens
        if tok and tok.strip(".,;:!?()[]{}")
    ]
    counts = Counter(
        t
        for t in tokens
        if t not in _KEYWORD_STOP_WORDS and not t.isdigit() and len(t) <= 24
    )
    return [word for word, _ in counts.most_common(max_items)]


def _extract_requirement_snippets(text: str, *, max_items: int = 8) -> list[str]:
    markers = (
        "must",
        "required",
        "responsible",
        "experience",
        "build",
        "design",
        "develop",
        "maintain",
        "optimiz",
        "architect",
        "collaborat",
        "own",
        "lead",
    )
    chunks = re.split(r"[\r\n]+|(?<=[.!?])\s+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for raw in chunks:
        s = re.sub(r"\s+", " ", raw or "").strip(" -\t*")
        if len(s) < 30:
            continue
        sl = s.lower()
        if not any(m in sl for m in markers):
            continue
        if len(s) > 180:
            s = s[:177].rstrip() + "..."
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_items:
            break
    if out:
        return out

    # Fallback: first meaningful lines/sentences when explicit requirement markers are absent.
    for raw in chunks:
        s = re.sub(r"\s+", " ", raw or "").strip(" -\t*")
        if len(s) < 40:
            continue
        if len(s) > 180:
            s = s[:177].rstrip() + "..."
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def _pick_term_for_snippet(snippet: str, terms: list[str]) -> str:
    s = (snippet or "").lower()
    for term in terms:
        if term in s:
            return term
    return terms[0] if terms else "core role skills"


def generate_interview_coach_fallback(
    *,
    resume_text: str,
    job_text: str,
) -> PremiumAIResult:
    """
    Deterministic fallback for interview prep when the external AI provider is unavailable.
    """
    job_terms = _extract_focus_terms(job_text, max_items=12)
    resume_terms = _extract_focus_terms(resume_text, max_items=40)
    requirement_snippets = _extract_requirement_snippets(job_text, max_items=8)
    resume_term_set = set(resume_terms)
    matched_terms = [t for t in job_terms if t in resume_term_set][:8]
    missing_terms = [t for t in job_terms if t not in resume_term_set][:8]
    focus_terms = job_terms[:6] or ["architecture", "apis", "reliability", "ownership", "debugging", "communication"]

    questions: list[Dict[str, Any]] = []

    for snippet in requirement_snippets:
        term = _pick_term_for_snippet(snippet, focus_terms)
        questions.append(
            {
                "type": "technical",
                "question": f'The job description emphasizes "{snippet}". Tell me about a project where you delivered this in production.',
                "why_they_ask": "This appears directly in the role requirements and is likely a day-one expectation.",
                "what_good_looks_like": [
                    "Explains scope, constraints, and personal ownership clearly",
                    "Connects implementation decisions to measurable outcomes",
                ],
                "red_flags": [
                    "Only high-level statements with no concrete execution details",
                    "No metrics, validation strategy, or lessons learned",
                ],
                "difficulty": "hard",
                "suggested_answer_outline": [
                    "Context and goal (what problem needed solving)",
                    "Your technical decisions and tradeoffs",
                    "Execution details and collaboration points",
                    "Result metrics and what you would improve next",
                ],
                "study_focus": [term],
            }
        )
        if len(questions) >= 8:
            break

    for term in focus_terms:
        if len(questions) >= 8:
            break
        questions.append(
            {
                "type": "technical",
                "question": f"How would you approach a production scenario in this role where {term} is a key requirement?",
                "why_they_ask": "To verify practical depth for a core skill in the posted role.",
                "what_good_looks_like": [
                    "Mentions concrete architecture and operational tradeoffs",
                    "Includes validation, monitoring, and rollback considerations",
                ],
                "red_flags": [
                    "No mention of reliability, observability, or testing",
                    "Unclear ownership and execution sequencing",
                ],
                "difficulty": "medium",
                "suggested_answer_outline": [
                    "Clarify constraints and success criteria",
                    "Propose implementation approach with tradeoffs",
                    "Describe rollout, monitoring, and failure handling",
                ],
                "study_focus": [term],
            }
        )

    if len(questions) < 8:
        questions.append(
            {
                "type": "role_fit",
                "question": "Based on this exact role, what would your 30/60/90 day execution plan look like?",
                "why_they_ask": "To test role alignment, prioritization, and impact planning.",
                "what_good_looks_like": [
                    "Priorities map to job requirements and team outcomes",
                    "Includes measurable checkpoints and collaboration plan",
                ],
                "red_flags": [
                    "Generic milestones with no tie to role requirements",
                    "No discussion of dependencies or risks",
                ],
                "difficulty": "medium",
                "suggested_answer_outline": [
                    "First 30 days: context and diagnostics",
                    "Next 30 days: implementation and quality gates",
                    "Final 30 days: optimization and measurable impact",
                ],
                "study_focus": focus_terms[:2],
            }
        )

    stories_source = requirement_snippets[:3] or [f"impact using {t}" for t in focus_terms[:3]]
    stories = []
    for s in stories_source:
        stories.append(
            {
                "story_prompt": f"Prepare a STAR story about {s}.",
                "STAR_outline": {
                    "S": "Describe the business context and constraints relevant to the role.",
                    "T": "State your objective and success criteria.",
                    "A": "Explain your actions, decisions, and tradeoffs.",
                    "R": "Share measurable impact and what you improved afterward.",
                },
            }
        )

    study_topics = (missing_terms[:5] or focus_terms[:5])[:5]
    study_materials = []
    for term in study_topics:
        priority = "high" if term in missing_terms[:3] else "medium"
        study_materials.append(
            {
                "topic": term,
                "priority": priority,
                "why_it_matters": f'"{term}" appears in the job requirements and is likely to be tested in screening and technical rounds.',
                "resources": [
                    f"Official documentation and best practices for {term}",
                    f"One end-to-end implementation example using {term}",
                    f"Common interview tradeoffs and failure modes for {term}",
                ],
                "practice_tasks": [
                    f"Build or outline a mini-project using {term}",
                    f"Prepare one STAR story demonstrating impact with {term}",
                ],
            }
        )

    recommendations = [
        "Prioritize answers that mirror exact language from the job description while staying truthful.",
        "Prepare metrics-first examples (latency, reliability, cost, conversion, delivery speed) for each key requirement.",
        "Use a consistent answer structure: context, actions/tradeoffs, measurable results, and learnings.",
    ]
    if missing_terms:
        recommendations.append(
            f"Close top skill gaps before interviews: {', '.join(missing_terms[:3])}."
        )

    preparation_plan = [
        {
            "label": "Day 1: Role deconstruction",
            "objective": "Map your best project evidence to explicit job requirements.",
            "actions": [
                "Highlight the 5-8 strongest requirement lines from the job post",
                "Attach one concrete project/result to each requirement",
            ],
        },
        {
            "label": "Day 2: Technical depth prep",
            "objective": "Strengthen weak areas likely to be tested in technical rounds.",
            "actions": [
                "Review top missing skills and key system design tradeoffs",
                "Prepare concise explanations of architecture, testing, and monitoring choices",
            ],
        },
        {
            "label": "Day 3: Mock interview run",
            "objective": "Practice role-specific answers with timing and clarity.",
            "actions": [
                "Run 8 role-specific questions aloud",
                "Refine stories to keep each answer under 2 minutes while preserving impact",
            ],
        },
    ]

    rubric = [
        {"dimension": "communication", "how_to_score": "Answers are structured, concise, and tailored to this job description."},
        {"dimension": "technical_depth", "how_to_score": "Demonstrates practical implementation detail and tradeoff reasoning for role-specific skills."},
        {"dimension": "ownership", "how_to_score": "Shows clear personal contribution, accountability, and execution leadership."},
        {"dimension": "impact", "how_to_score": "Connects work to measurable outcomes relevant to business/team goals."},
        {"dimension": "role_alignment", "how_to_score": "Directly maps experience to the posted must-haves and responsibilities."},
    ]

    next_steps = [
        "Finalize 6-8 role-specific stories tied to requirements in this posting.",
        "Practice answering each technical question using concrete architecture and outcome details.",
        "Prepare a short study sprint for any missing skills before live interviews.",
    ]
    gap_analysis = {
        "matched": matched_terms,
        "missing": missing_terms,
        "notes": [
            "Matched skills appear in both your resume and this job description.",
            "Missing skills are inferred from role language and should be prioritized for prep.",
        ],
    }

    normalized = _normalize_interview_coach_payload(
        {
            "questions": questions,
            "rubric": rubric,
            "suggested_stories": stories,
            "recommendations": recommendations,
            "study_materials": study_materials,
            "preparation_plan": preparation_plan,
            "gap_analysis": gap_analysis,
            "next_steps": next_steps,
        }
    )
    return PremiumAIResult(
        response_json=normalized,
        model="fallback:interview-v2",
        tokens_used=0,
    )


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
        max_tokens=int(getattr(settings, "premium_ai_max_tokens_interview", 2200)),
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
Create a HIGHLY JOB-SPECIFIC interview prep pack tailored to this exact resume and job description.

RESUME (trimmed):
{resume_text[:9000]}

JOB DESCRIPTION (trimmed):
{job_text[:9000]}

Return JSON with this exact shape:
{{
  "questions": [
    {{
      "type": "behavioral|technical|system_design|role_fit",
      "question": "...",
      "why_they_ask": "...",
      "what_good_looks_like": ["...", "..."],
      "red_flags": ["...", "..."],
      "difficulty": "easy|medium|hard",
      "suggested_answer_outline": ["...", "..."],
      "study_focus": ["...", "..."]
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
      "story_prompt": "...",
      "STAR_outline": {{"S":"...","T":"...","A":"...","R":"..."}}
    }}
  ],
  "recommendations": ["...", "..."],
  "study_materials": [
    {{
      "topic": "...",
      "priority": "high|medium|low",
      "why_it_matters": "...",
      "resources": ["...", "..."],
      "practice_tasks": ["...", "..."]
    }}
  ],
  "preparation_plan": [
    {{
      "label": "...",
      "objective": "...",
      "actions": ["...", "..."]
    }}
  ],
  "gap_analysis": {{
    "matched": ["..."],
    "missing": ["..."],
    "notes": ["..."]
  }},
  "next_steps": ["...", "..."]
}}

Hard constraints:
- Every question must map to explicit requirements from the job description.
- Avoid generic interview questions unless they are tied back to this role.
- Include 8-12 questions with at least:
  - 3 technical role-specific questions
  - 2 behavioral questions tied to likely responsibilities
  - 1 system-design/architecture question if relevant
- Keep content concise and practical (1-3 sentences per text field).
"""

    def _extract_payload(response: Any) -> Optional[Dict[str, Any]]:
        if not response:
            return None
        if isinstance(response.json_data, dict):
            return response.json_data
        return _try_parse_json_object(str(response.content or ""))

    tokens_used = 0
    resp = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    tokens_used += int(resp.tokens_used or 0)
    payload = _extract_payload(resp)

    if payload is None:
        # Retry once with a compact schema to reduce malformed/truncated JSON responses.
        retry_prompt = f"""
Generate a compact, HIGHLY JOB-SPECIFIC interview prep JSON using this schema only:
{{
  "questions":[{{"type":"technical|behavioral|system_design|role_fit","question":"...","why_they_ask":"...","what_good_looks_like":["..."],"red_flags":["..."],"difficulty":"easy|medium|hard","suggested_answer_outline":["..."],"study_focus":["..."]}}],
  "rubric":[{{"dimension":"communication|technical_depth|ownership|impact|role_alignment","how_to_score":"..."}}],
  "suggested_stories":[{{"story_prompt":"...","STAR_outline":{{"S":"...","T":"...","A":"...","R":"..."}}}}],
  "recommendations":["..."],
  "study_materials":[{{"topic":"...","priority":"high|medium|low","why_it_matters":"...","resources":["..."],"practice_tasks":["..."]}}],
  "preparation_plan":[{{"label":"...","objective":"...","actions":["..."]}}],
  "gap_analysis":{{"matched":["..."],"missing":["..."],"notes":["..."]}},
  "next_steps":["..."]
}}

Rules:
- 6-8 role-specific questions tied directly to the job requirements.
- Prefer shorter fields over verbose prose.

RESUME:
{resume_text[:6000]}

JOB DESCRIPTION:
{job_text[:6000]}
"""
        retry = await client.complete(retry_prompt, system_prompt=system_prompt, json_mode=True)
        tokens_used += int(retry.tokens_used or 0)
        payload = _extract_payload(retry)
        if payload is None:
            err = retry.error or resp.error
            if not err:
                err = "AI returned malformed interview prep data"
            raise RuntimeError(err)

    normalized = _normalize_interview_coach_payload(payload)
    if not normalized["questions"] and not normalized["rubric"]:
        raise RuntimeError("AI returned empty interview prep content")

    return PremiumAIResult(
        response_json=normalized,
        model=settings.openai_model,
        tokens_used=tokens_used,
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

    if not isinstance(resp.json_data, dict):
        raise RuntimeError("AI returned malformed template data")

    normalized = _normalize_template_payload(
        resp.json_data, template_id=template_id_norm, tone=tone_norm, fallback_content=resp.content
    )
    if not normalized.get("content"):
        raise RuntimeError("AI returned empty template content")

    return PremiumAIResult(
        response_json=normalized,
        model=settings.openai_model,
        tokens_used=int(resp.tokens_used or 0),
    )

