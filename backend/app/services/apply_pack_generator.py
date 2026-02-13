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
            client, resume_text, job_description, resume_analysis, job_analysis,
            learning_context=learning_context
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
    learning_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate tailored professional summary."""
    system_prompt = """You are a career coach helping job seekers tailor their resumes.
Write concise, professional summaries that highlight relevant experience."""
    
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
    
    # Safely extract lists
    skills = _ensure_list(resume_analysis.get('skills'), 10)
    bullets = _ensure_list(resume_analysis.get('bullets'))
    must_haves = _ensure_list(job_analysis.get('must_haves'), 5)
    keywords = _ensure_list(job_analysis.get('keywords'), 10)
    
    prompt = f"""Write a 2-3 sentence professional summary that matches this resume to this job.

Resume highlights:
- Skills: {', '.join(str(s) for s in skills)}
- Seniority: {resume_analysis.get('seniority', 'mid')}
- Key achievements: {len(bullets)} quantified results

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

Summary:"""
    
    response = await client.complete(prompt, system_prompt=system_prompt)
    if response.ok:
        return response.content.strip()
    return "Experienced professional with relevant skills and proven track record."


async def _generate_bullets(
    client,
    resume_analysis: Dict,
    job_analysis: Dict,
    learning_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate tailored resume bullets."""
    system_prompt = """You are a resume writer. Rewrite achievement bullets to match job requirements.
Include quantified metrics and impact."""
    
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
{
  "bullets": [
    {"text": "Rewritten bullet point", "match_score": 85}
  ]
}

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
    
    resume_skills = _ensure_list(resume_analysis.get('skills'), 10)
    
    prompt = f"""Write a professional, hyper-personalized cover letter (3-5 short paragraphs) for this job application.

JOB DETAILS:
- Position: {job_title or 'This role'}
- Company: {company_name or 'Your organization'}
{company_context}
- Key Requirements: {', '.join(str(m) for m in must_haves) if must_haves else 'See job description'}
- Important Keywords: {', '.join(str(k) for k in keywords) if keywords else 'N/A'}
- Role Expectations: {rubric[:300] if rubric else 'See job description'}

MY BACKGROUND:
- Skills: {', '.join(str(s) for s in resume_skills)}
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
    skills = _ensure_list(resume_analysis.get('skills'), 10)
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
