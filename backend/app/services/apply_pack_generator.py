"""
Apply Pack generation service.

Generates tailored resume content, cover note, and ATS checklist.
"""

from typing import Dict, List, Optional, Any
import re
import json

from backend.app.core.config import get_settings


def _ensure_list(value: Any, max_items: int = None) -> List:
    """Ensure value is a list, handling JSON strings and None."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = []
        except (json.JSONDecodeError, TypeError):
            value = []
    if not isinstance(value, list):
        try:
            value = list(value)
        except (TypeError, ValueError):
            value = []
    if max_items is not None:
        return value[:max_items]
    return value


_GENERIC_SKILL_TOKENS = {
    "skill",
    "skills",
    "experience",
    "professional",
    "software",
    "engineering",
    "developer",
    "development",
    "technology",
    "technologies",
}


def _clean_skills_list(skills: Any, max_items: int = 12) -> List[str]:
    raw = _ensure_list(skills)
    out: List[str] = []
    seen = set()
    for s in raw:
        t = str(s or "").strip()
        if not t:
            continue
        tl = t.lower()
        if tl in _GENERIC_SKILL_TOKENS:
            continue
        if len(t) < 2:
            continue
        if tl in seen:
            continue
        seen.add(tl)
        out.append(t)
        if len(out) >= max_items:
            break
    return out


def _fallback_skills_from_text(resume_text: str, max_items: int = 8) -> List[str]:
    """
    Lightweight, deterministic fallback for when resume analysis returns junk like ["skills"].
    Keep it conservative (only well-known tech keywords).
    """
    text_lower = (resume_text or "").lower()
    candidates = [
        "Python",
        "TypeScript",
        "JavaScript",
        "Node.js",
        "React",
        "FastAPI",
        "Flask",
        "Django",
        "PostgreSQL",
        "MySQL",
        "Docker",
        "Kubernetes",
        "Terraform",
        "AWS",
        "GCP",
        "Azure",
        "LangChain",
        "RAG",
        "Pinecone",
        "n8n",
        "Zapier",
        "GitHub Actions",
    ]
    out: List[str] = []
    for c in candidates:
        if c.lower() in text_lower:
            out.append(c)
        if len(out) >= max_items:
            break
    return out


async def generate_apply_pack(
    resume_text: str,
    resume_analysis: Dict[str, Any],
    job_description: str,
    job_analysis: Dict[str, Any],
    use_ai: bool = True,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
    company_summary: Optional[str] = None,
    company_website: Optional[str] = None,
    learning_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate tailored apply pack content.
    
    Returns:
        {
            "tailored_summary": str,
            "tailored_bullets": List[Dict],  # [{"text": "...", "match_score": 0-100}]
            "cover_note": str,
            "ats_checklist": {
                "keyword_coverage": float,  # 0-100
                "matched_skills": List[str],
                "missing_skills": List[str],
            },
            "keyword_coverage": float,  # 0-100
        }
    """
    if not use_ai:
        # Basic template-based generation
        return _generate_basic_pack(resume_analysis, job_analysis, job_title=job_title, company_name=company_name)
    
    # Use AI for generation
    settings = get_settings()
    if not settings.openai_api_key:
        return _generate_basic_pack(resume_analysis, job_analysis, job_title=job_title, company_name=company_name)
    
    try:
        from jobscout.llm.provider import LLMConfig, get_llm_client
        
        llm_config = LLMConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=3000,
            temperature=0.3,  # Slightly higher for creativity
        )
        
        client = get_llm_client(llm_config)
        if not client:
            return _generate_basic_pack(resume_analysis, job_analysis)
        
        # Generate tailored summary (with learning context)
        summary = await _generate_summary(
            client,
            resume_text,
            job_description,
            resume_analysis,
            job_analysis,
            job_title=job_title,
            learning_context=learning_context,
        )
        
        # Generate tailored bullets (with learning context)
        bullets = await _generate_bullets(
            client, resume_analysis, job_analysis,
            learning_context=learning_context
        )
        
        # Generate cover note (with learning context)
        cover_note = await _generate_cover_note(
            client, 
            resume_analysis, 
            job_analysis,
            job_title=job_title,
            company_name=company_name,
            company_summary=company_summary,
            company_website=company_website,
            learning_context=learning_context,
        )
        
        # Calculate ATS checklist
        ats_checklist = _calculate_ats_checklist(resume_analysis, job_analysis)

        # AI-optimize experience bullets (truth-preserving rewrite) to improve ATS + human review.
        optimized_experience = await _generate_optimized_experience(
            client,
            resume_text=resume_text,
            resume_analysis=resume_analysis,
            job_analysis=job_analysis,
            job_title=job_title,
        )
        if optimized_experience:
            ats_checklist["optimized_experience"] = optimized_experience

        # Full AI-crafted resume structure for premium + ATS-safe export (best-effort).
        optimized_resume = await _generate_optimized_resume_structure(
            client,
            resume_text=resume_text,
            resume_analysis=resume_analysis,
            job_analysis=job_analysis,
            job_title=job_title,
            job_description=job_target.get("description_text", request.job_text or ""),
            tailored_summary=summary,
            tailored_bullets=bullets,
        )
        if optimized_resume:
            ats_checklist["optimized_resume"] = optimized_resume
        
        return {
            "tailored_summary": summary,
            "tailored_bullets": bullets,
            "cover_note": cover_note,
            "ats_checklist": ats_checklist,
            "keyword_coverage": ats_checklist["keyword_coverage"],
        }
        
    except Exception as e:
        print(f"Error in AI apply pack generation: {e}")
        return _generate_basic_pack(resume_analysis, job_analysis)


async def _generate_summary(
    client,
    resume_text: str,
    job_description: str,
    resume_analysis: Dict,
    job_analysis: Dict,
    job_title: Optional[str] = None,
    learning_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate tailored professional summary."""
    system_prompt = """You are a meticulous ATS resume writer.
Write concise, keyword-aligned summaries that remain truthful.
Do not invent skills/tools/employers. Prefer plain ASCII punctuation."""
    
    # Build learning context string
    learning_str = ""
    if learning_context:
        if learning_context.get("top_skills_gaps"):
            learning_str += f"\n\nIMPORTANT: Past feedback shows skills gaps in: {', '.join(learning_context.get('top_skills_gaps', [])[:5])}. "
            learning_str += "If you have these skills, make sure to highlight them prominently. If not, consider how your existing skills relate."
        if learning_context.get("recurring_issues"):
            issues = learning_context.get("recurring_issues", [])
            if "seniority" in issues:
                learning_str += "\nNote: Past applications were rejected due to seniority mismatch. Ensure the summary clearly matches the required seniority level."
            if "skills_gap" in issues:
                learning_str += "\nNote: Past applications were rejected due to skills gaps. Emphasize relevant skills and experience."
    
    # Safely extract lists (and clean "skills"-placeholder junk)
    skills = _clean_skills_list(resume_analysis.get("skills"), 10)
    if not skills:
        skills = _fallback_skills_from_text(resume_text, max_items=8)
    bullets = _ensure_list(resume_analysis.get('bullets'))
    sample_achievements = []
    for b in bullets[:4]:
        if isinstance(b, dict):
            txt = str(b.get("text") or "").strip()
        else:
            txt = str(b).strip()
        if txt:
            sample_achievements.append(txt)
    must_haves = _ensure_list(job_analysis.get('must_haves'), 5)
    keywords = _ensure_list(job_analysis.get('keywords'), 10)
    
    prompt = f"""Write a 2-3 sentence ATS-friendly professional summary that matches this resume to this job.

Resume highlights:
- Skills: {', '.join(str(s) for s in skills) if skills else 'N/A'}
- Target role: {job_title or 'N/A'}
- Seniority: {resume_analysis.get('seniority', 'mid')}
- Key achievements: {len(bullets)} quantified results
 - Example achievements (verbatim): {' | '.join(sample_achievements[:2]) if sample_achievements else 'N/A'}

Job requirements:
- Must-haves: {', '.join(str(m) for m in must_haves)}
- Keywords: {', '.join(str(k) for k in keywords)}
{learning_str}

Write a summary that:
1. Highlights relevant experience and skills
2. Mentions key achievements if relevant
3. Shows alignment with job requirements
4. Is specific and avoids generic phrases
5. Addresses any past feedback patterns mentioned above
6. Uses simple punctuation (avoid fancy dashes/quotes)
7. Avoids keyword stuffing; include only keywords that are true for the candidate
8. Mentions at least one concrete outcome/metric from the resume if available

Summary:"""
    
    response = await client.complete(prompt, system_prompt=system_prompt)
    if response.ok:
        out = (response.content or "").strip()
        out_l = out.lower()
        # Guardrail against placeholders/generic output that requires manual edits.
        if (
            out
            and "expertise in skills" not in out_l
            and not out_l.endswith("in skills.")
            and not out_l.startswith("experienced professional with relevant skills")
        ):
            return out

    seniority = str(resume_analysis.get("seniority", "professional") or "professional").strip()
    top = skills[:4]
    role = (job_title or "professional").strip()
    if top:
        return f"{seniority.capitalize()} {role} with expertise in {', '.join(top)} and a track record of delivering measurable outcomes."
    return f"{seniority.capitalize()} {role} with a track record of delivering measurable outcomes aligned to the role requirements."


async def _generate_bullets(
    client,
    resume_analysis: Dict,
    job_analysis: Dict,
    learning_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate tailored resume bullets."""
    system_prompt = """You are a meticulous ATS resume bullet writer.
Rewrite bullets to match job requirements while staying truthful.
Do not add skills/tools not supported by the original bullets or resume analysis.
Prefer simple punctuation (no fancy dashes/quotes)."""
    
    existing_bullets = _ensure_list(resume_analysis.get('bullets'), 5)
    if not existing_bullets:
        return []
    
    bullets_text = "\n".join([f"- {b.get('text', '') if isinstance(b, dict) else str(b)}" for b in existing_bullets])
    
    # Build learning context string
    learning_str = ""
    if learning_context:
        if learning_context.get("top_skills_gaps"):
            learning_str += f"\n\nIMPORTANT: Past feedback shows skills gaps in: {', '.join(learning_context.get('top_skills_gaps', [])[:5])}. "
            learning_str += "If any bullets demonstrate these skills, emphasize them strongly. If not, consider reframing achievements to highlight related capabilities."
        if learning_context.get("positive_signals"):
            learning_str += f"\nNote: Past successful applications emphasized: {', '.join(learning_context.get('positive_signals', [])[:3])}. "
            learning_str += "Consider highlighting similar patterns in these bullets."
    
    job_keywords = _ensure_list(job_analysis.get('keywords'), 15)
    job_must_haves = _ensure_list(job_analysis.get('must_haves'), 5)
    
    prompt = f"""Rewrite these resume bullets to better match this job. Keep the core achievements but emphasize relevant skills and impact.

Job keywords: {', '.join(str(k) for k in job_keywords)}
Job must-haves: {', '.join(str(m) for m in job_must_haves)}
{learning_str}

Current bullets:
{bullets_text}

Return a JSON object with this shape:
{{
  "bullets": [
    {{"text": "Rewritten bullet point", "match_score": 85}}
  ]
}}

Each bullet should:
- Keep original metrics/numbers
- Emphasize skills mentioned in job
- Be specific and action-oriented
- Have a match_score (0-100) indicating relevance
- Address any past feedback patterns mentioned above"""
    
    response = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    
    if response.ok and response.json_data:
        parsed = response.json_data
        if isinstance(parsed, dict) and isinstance(parsed.get("bullets"), list):
            bullets = parsed.get("bullets") or []
            return bullets[:5]
        # Backwards compatibility if model returned a top-level array despite JSON mode constraints
        if isinstance(parsed, list):
            return parsed[:5]
    
    # Fallback: return original bullets with basic scores
    return [
        {"text": b.get("text", "") if isinstance(b, dict) else str(b), "match_score": 70}
        for b in existing_bullets
    ]


def _score_experience_relevance(exp: Dict[str, Any], keywords: List[str]) -> int:
    text = " ".join(
        [
            str(exp.get("title") or ""),
            str(exp.get("company") or ""),
            str(exp.get("location") or ""),
            " ".join([str(x) for x in (exp.get("bullets") or [])]),
        ]
    ).lower()
    score = 0
    for k in keywords[:20]:
        kl = str(k or "").lower().strip()
        if not kl:
            continue
        if kl in text:
            score += 1
    return score


async def _generate_optimized_experience(
    client,
    *,
    resume_text: str,
    resume_analysis: Dict[str, Any],
    job_analysis: Dict[str, Any],
    job_title: Optional[str],
) -> Optional[List[Dict[str, Any]]]:
    """
    Rewrite experience bullets to be outcome-driven and keyword-aligned while staying truthful.
    Output is used for DOCX export only; it does not change stored resume text.
    """
    try:
        from backend.app.services import docx_generator
    except Exception:
        return None

    parsed = docx_generator._parse_resume_into_structure(resume_text or "") if resume_text else {}
    experience = parsed.get("experience") if isinstance(parsed, dict) else None
    if not isinstance(experience, list) or not experience:
        return None

    job_keywords = _ensure_list(job_analysis.get("keywords"), 20)
    must_haves = _ensure_list(job_analysis.get("must_haves"), 10)
    all_terms = [str(x) for x in (must_haves + job_keywords) if str(x or "").strip()]

    # Pick up to 4 most relevant roles to optimize (cost guardrail)
    ranked = sorted(experience, key=lambda e: _score_experience_relevance(e if isinstance(e, dict) else {}, all_terms), reverse=True)
    selected = []
    for e in ranked:
        if not isinstance(e, dict):
            continue
        bullets = e.get("bullets") or []
        if not isinstance(bullets, list) or not bullets:
            continue
        selected.append(
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "location": e.get("location", ""),
                "dates": e.get("dates", ""),
                "bullets": [str(b) for b in bullets[:6] if str(b or "").strip()],
            }
        )
        if len(selected) >= 4:
            break
    if not selected:
        return None

    allowed_skills = _clean_skills_list(resume_analysis.get("skills"), 25)

    system_prompt = (
        "You are an expert resume editor. Rewrite bullets to be outcome-driven and ATS-friendly, "
        "while remaining strictly truthful. Do not invent skills, tools, metrics, employers, or scope."
    )

    import json
    selected_json = json.dumps(selected, ensure_ascii=True)

    prompt = f"""
Rewrite the EXPERIENCE bullets below for ATS + human reviewers.

CONTEXT:
- Target role: {job_title or 'N/A'}
- Job must-haves: {', '.join(str(x) for x in must_haves[:8])}
- Job keywords: {', '.join(str(x) for x in job_keywords[:12])}
- Allowed skills/tools (from resume analysis): {', '.join(allowed_skills[:20]) if allowed_skills else 'N/A'}

INPUT EXPERIENCE (verbatim):
{selected_json}

Rules:
- Keep each role's title/company/location/dates unchanged.
- Rewrite bullets to be clearer and more outcome-driven.
- Preserve all numbers/metrics exactly; do not add new metrics.
- Do NOT add new tools/skills not already present in the input bullets or allowed skills/tools list.
- Use past tense, active voice, and simple punctuation.
- 3-6 bullets per role; you may merge/split bullets only if it does not change meaning.
- Each role must include at least 2 bullets that directly map to job must-haves/keywords (where applicable).
- Output must be valid JSON only.

Return JSON with this exact shape:
{{
  "experience": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "dates": "...",
      "bullets": ["...", "..."]
    }}
  ]
}}
"""

    resp = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    if not resp or not getattr(resp, "ok", False) or not getattr(resp, "json_data", None):
        return None
    data = resp.json_data
    if not isinstance(data, dict) or not isinstance(data.get("experience"), list):
        return None
    out: List[Dict[str, Any]] = []
    for e in data.get("experience", [])[:4]:
        if not isinstance(e, dict):
            continue
        bullets = e.get("bullets")
        if not isinstance(bullets, list) or not bullets:
            continue
        clean_bullets = []
        for b in bullets[:6]:
            bt = str(b or "").strip()
            if bt:
                clean_bullets.append(bt)
        if not clean_bullets:
            continue
        out.append(
            {
                "title": str(e.get("title") or ""),
                "company": str(e.get("company") or ""),
                "location": str(e.get("location") or ""),
                "dates": str(e.get("dates") or ""),
                "bullets": clean_bullets[:6],
            }
        )
    return out or None


def _extract_numeric_tokens(text: str) -> set[str]:
    """
    Extract numeric-ish tokens to prevent the model from inventing metrics.
    Examples: 99.9%, 20-50+, 34%, 18, 18h, 2x, $10K
    """
    t = (text or "").lower()
    tokens = set()
    for m in re.findall(r"(?<![a-z0-9])(\$?\d[\d\.,]*\+?(?:-\d[\d\.,]*\+?)?(?:%|x|k|m|b)?)(?![a-z0-9])", t):
        if m:
            tokens.add(m)
    return tokens


async def _generate_optimized_resume_structure(
    client,
    *,
    resume_text: str,
    resume_analysis: Dict[str, Any],
    job_analysis: Dict[str, Any],
    job_title: Optional[str],
    job_description: str,
    tailored_summary: str,
    tailored_bullets: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Generate a full, premium-feeling but ATS-safe structured resume.
    Renderer remains deterministic; this function only shapes content.
    """
    try:
        from backend.app.services import docx_generator
    except Exception:
        return None

    parsed = docx_generator._parse_resume_into_structure(resume_text or "") if resume_text else {}
    if not isinstance(parsed, dict) or not parsed:
        return None

    must_haves = _ensure_list(job_analysis.get("must_haves"), 10)
    keywords = _ensure_list(job_analysis.get("keywords"), 20)
    allowed_skills = _clean_skills_list(resume_analysis.get("skills"), 30)

    # Anti-hallucination: keep a set of numeric tokens present in the original resume text
    allowed_numbers = _extract_numeric_tokens(resume_text or "")

    import json
    parsed_json = json.dumps(parsed, ensure_ascii=True)
    tailored_bullets_json = json.dumps(tailored_bullets or [], ensure_ascii=True)

    system_prompt = (
        "You are an expert resume writer. Produce ATS-friendly, premium-feeling resumes. "
        "Be precise and truthful: do not invent employers, roles, dates, tools, or metrics."
    )

    prompt = f"""
Create an ATS-friendly resume STRUCTURE from the input resume. Improve clarity, ordering, and bullet quality.

TARGET ROLE:
{job_title or 'N/A'}

JOB REQUIREMENTS:
- Must-haves: {', '.join(str(x) for x in must_haves[:8])}
- Keywords: {', '.join(str(x) for x in keywords[:15])}
 - Job phrasing (verbatim excerpt, use for tone/wording only): {(job_description or '')[:700]}

ALLOWED SKILLS/TOOLS (from analysis; do not add tools outside this list unless they already appear in the input resume):
{', '.join(allowed_skills) if allowed_skills else 'N/A'}

INPUT RESUME STRUCTURE (verbatim JSON, extracted from the resume text):
{parsed_json}

TAILORED SUMMARY (use as the summary base; you may tighten it):
{tailored_summary}

TAILORED KEY ACHIEVEMENTS (use as the achievements base; you may tighten them):
{tailored_bullets_json}

Rules:
- Keep name/contact info and role history truthful; do not invent anything.
- Prefer 2-3 sentence summary with 1 concrete metric/outcome when available.
- Key Achievements: 3-5 bullets, outcome-driven, simple punctuation.
- Skills: group into 3-6 categories, order categories by relevance to the job.
- Experience: 4-6 bullets per role; outcome-driven; keep all numbers the same as input (no new numbers).
- Each role must include 1-2 bullets using job-specific phrasing from the job description excerpt (without inventing facts).
- Projects: 1-2 bullets each if present; keep URLs if present.
- Keep section names: summary, key_achievements, skills, experience, projects, education, certifications.
- Output must be valid JSON only.

Return JSON with this exact shape:
{{
  "summary": "string",
  "key_achievements": ["...", "..."],
  "skills": [{{"category": "Category", "items": ["...", "..."]}}],
  "experience": [{{"title": "", "company": "", "location": "", "dates": "", "bullets": ["..."]}}],
  "projects": [{{"name": "", "url": "", "bullets": ["..."]}}],
  "education": [{{"degree": "", "school": "", "dates": ""}}],
  "certifications": [{{"name": "", "issuer": "", "date": ""}}]
}}
"""

    resp = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    if not resp or not getattr(resp, "ok", False) or not getattr(resp, "json_data", None):
        return None
    data = resp.json_data
    if not isinstance(data, dict):
        return None

    # Post-validate: drop bullets that introduce numeric tokens not present in original resume_text
    def _filter_bullets(bullets_any: Any) -> List[str]:
        bullets_list = bullets_any if isinstance(bullets_any, list) else []
        out: List[str] = []
        for b in bullets_list[:8]:
            bt = str(b or "").strip()
            if not bt:
                continue
            new_nums = _extract_numeric_tokens(bt) - allowed_numbers
            if new_nums:
                continue
            out.append(bt)
        return out

    cleaned: Dict[str, Any] = {}
    if isinstance(data.get("summary"), str):
        cleaned["summary"] = data.get("summary")
    if isinstance(data.get("key_achievements"), list):
        cleaned["key_achievements"] = _filter_bullets(data.get("key_achievements"))[:5]
    if isinstance(data.get("skills"), list):
        skills_out = []
        for g in data.get("skills")[:8]:
            if not isinstance(g, dict):
                continue
            cat = str(g.get("category") or "").strip()
            items = [str(x or "").strip() for x in (g.get("items") or []) if str(x or "").strip()]
            if not items:
                continue
            skills_out.append({"category": cat or None, "items": items[:12]})
        cleaned["skills"] = skills_out
    if isinstance(data.get("experience"), list):
        exp_out = []
        for e in data.get("experience")[:6]:
            if not isinstance(e, dict):
                continue
            bullets = _filter_bullets(e.get("bullets"))
            if not bullets:
                continue
            exp_out.append(
                {
                    "title": str(e.get("title") or ""),
                    "company": str(e.get("company") or ""),
                    "location": str(e.get("location") or ""),
                    "dates": str(e.get("dates") or ""),
                    "bullets": bullets[:6],
                }
            )
        cleaned["experience"] = exp_out
    if isinstance(data.get("projects"), list):
        proj_out = []
        for p in data.get("projects")[:6]:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name") or "").strip()
            url = str(p.get("url") or "").strip()
            if not name:
                # Don't emit anonymous projects; they render poorly and look unpolished.
                continue
            bullets = _filter_bullets(p.get("bullets"))[:3]
            proj_out.append(
                {
                    "name": name,
                    "url": url,
                    "bullets": bullets,
                }
            )
        cleaned["projects"] = proj_out
    if isinstance(data.get("education"), list):
        edu_out = []
        for e in data.get("education")[:6]:
            if not isinstance(e, dict):
                continue
            edu_out.append(
                {
                    "degree": str(e.get("degree") or ""),
                    "school": str(e.get("school") or ""),
                    "dates": str(e.get("dates") or ""),
                }
            )
        cleaned["education"] = edu_out
    if isinstance(data.get("certifications"), list):
        cert_out = []
        for c in data.get("certifications")[:8]:
            if not isinstance(c, dict):
                continue
            cert_out.append(
                {
                    "name": str(c.get("name") or ""),
                    "issuer": str(c.get("issuer") or ""),
                    "date": str(c.get("date") or ""),
                }
            )
        cleaned["certifications"] = cert_out

    return cleaned or None


async def _generate_cover_note(
    client,
    resume_analysis: Dict,
    job_analysis: Dict,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
    company_summary: Optional[str] = None,
    company_website: Optional[str] = None,
    learning_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate hyper-personalized cover letter."""
    system_prompt = """You are a professional career coach and cover letter writer. Write compelling, personalized cover letters that demonstrate genuine interest and alignment with the company's values and the role's requirements."""
    
    # Build company context
    company_context = ""
    if company_name:
        company_context += f"Company: {company_name}\n"
    if company_website:
        company_context += f"Website: {company_website}\n"
    if company_summary:
        company_context += f"Company Overview: {company_summary[:300]}\n"
    
    # Get top resume achievements
    top_bullets = _ensure_list(resume_analysis.get('bullets'), 3)
    achievements_text = "\n".join([f"- {b.get('text', '') if isinstance(b, dict) else str(b)}" for b in top_bullets])
    
    # Build job requirements context
    must_haves = _ensure_list(job_analysis.get('must_haves'), 5)
    keywords = _ensure_list(job_analysis.get('keywords'), 10)
    rubric = job_analysis.get('rubric', '') or ''
    
    # Build learning context string
    learning_str = ""
    if learning_context:
        if learning_context.get("recurring_issues"):
            issues = learning_context.get("recurring_issues", [])
            if "seniority" in issues:
                learning_str += "\n\nIMPORTANT: Past applications were rejected due to seniority mismatch. "
                learning_str += "Ensure the cover letter clearly demonstrates that your experience level matches the role requirements."
            if "skills_gap" in issues:
                learning_str += "\nNote: Past applications were rejected due to skills gaps. "
                learning_str += "If you have the required skills, emphasize them clearly. If not, show how your existing skills transfer."
        if learning_context.get("top_skills_gaps"):
            learning_str += f"\nPast feedback indicates gaps in: {', '.join(learning_context.get('top_skills_gaps', [])[:3])}. "
            learning_str += "Address how your experience relates to these areas."
        if learning_context.get("positive_signals"):
            learning_str += f"\nPast successful applications emphasized: {', '.join(learning_context.get('positive_signals', [])[:3])}. "
            learning_str += "Consider highlighting similar strengths."
    
    resume_skills = _clean_skills_list(resume_analysis.get("skills"), 10)
    
    prompt = f"""Write a professional, hyper-personalized cover letter (3-5 short paragraphs) for this job application.

JOB DETAILS:
- Position: {job_title or 'This role'}
- Company: {company_name or 'Your organization'}
{company_context}
- Key Requirements: {', '.join(str(m) for m in must_haves) if must_haves else 'See job description'}
- Important Keywords: {', '.join(str(k) for k in keywords) if keywords else 'N/A'}
- Role Expectations: {rubric[:300] if rubric else 'See job description'}

MY BACKGROUND:
- Skills: {', '.join(str(s) for s in resume_skills) if resume_skills else 'N/A'}
- Seniority Level: {resume_analysis.get('seniority', 'mid')}
- Top Achievements:
{achievements_text if achievements_text else '- See resume for details'}
{learning_str}

JOB DESCRIPTION SUMMARY:
{job_analysis.get('rubric', job_description[:500] if 'job_description' in locals() else 'See full job description')}

Write a cover letter that:
1. Opens with genuine interest in the specific role and company (reference company values/culture if available)
2. Demonstrates alignment with role expectations by highlighting 2-3 most relevant achievements from my background
3. Shows understanding of key requirements and how my experience addresses them
4. Closes with enthusiasm and a clear call to action
5. Addresses any past feedback patterns mentioned above

Make it specific, authentic, and tailored - avoid generic phrases. Use the company name and role title naturally throughout.

Cover letter:"""
    
    response = await client.complete(prompt, system_prompt=system_prompt)
    if response.ok:
        return response.content.strip()
    # Fallback to basic template
    fallback = f"I am writing to express my strong interest in the {job_title or 'position'} at {company_name or 'your organization'}."
    if top_bullets:
        first_bullet_text = top_bullets[0].get('text', '') if isinstance(top_bullets[0], dict) else str(top_bullets[0])
        fallback += f" With my experience in {', '.join(str(s) for s in resume_skills[:3])} and proven track record including {first_bullet_text[:100]}..., I am confident I can contribute to your team's success."
    fallback += " I am excited about the opportunity to discuss how my background aligns with your requirements."
    return fallback


def _calculate_ats_checklist(
    resume_analysis: Dict,
    job_analysis: Dict,
) -> Dict[str, Any]:
    """Calculate ATS keyword coverage and missing skills."""
    skills_list = _ensure_list(resume_analysis.get('skills'))
    keywords_list = _ensure_list(job_analysis.get('keywords'))
    must_haves_list = _ensure_list(job_analysis.get('must_haves'))
    
    resume_skills = set(str(s).lower() for s in skills_list)
    job_keywords = set(str(k).lower() for k in keywords_list)
    job_must_haves = set(str(m).lower() for m in must_haves_list)
    
    # Find matches
    matched_skills = list(resume_skills.intersection(job_keywords))
    missing_skills = list(job_keywords - resume_skills)
    
    # Calculate coverage
    if job_keywords:
        coverage = (len(matched_skills) / len(job_keywords)) * 100
    else:
        coverage = 0.0
    
    return {
        "keyword_coverage": round(coverage, 1),
        "matched_skills": matched_skills[:20],
        "missing_skills": missing_skills[:20],
    }


def _generate_basic_pack(
    resume_analysis: Dict,
    job_analysis: Dict,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate basic pack without AI."""
    skills = _clean_skills_list(resume_analysis.get("skills"), 10)
    bullets = _ensure_list(resume_analysis.get('bullets'), 3)
    
    skills_str = ', '.join(str(s) for s in skills[:5]) if skills else 'relevant technologies'
    summary = f"Experienced {resume_analysis.get('seniority', 'professional')} with expertise in {skills_str}."
    
    tailored_bullets = [
        {"text": b.get("text", "") if isinstance(b, dict) else str(b), "match_score": 60}
        for b in bullets
    ]
    
    # Basic cover note fallback (still personalized if job_title/company available)
    cover_note = f"I am writing to express my interest in this position"
    if job_title:
        cover_note += f" as {job_title}"
    if company_name:
        cover_note += f" at {company_name}"
    skills_short = ', '.join(str(s) for s in skills[:3]) if skills else 'my skills'
    cover_note += f". With my experience in {skills_short}, I believe I can contribute effectively to your team."
    
    ats_checklist = _calculate_ats_checklist(resume_analysis, job_analysis)
    
    return {
        "tailored_summary": summary,
        "tailored_bullets": tailored_bullets,
        "cover_note": cover_note,
        "ats_checklist": ats_checklist,
        "keyword_coverage": ats_checklist["keyword_coverage"],
    }
