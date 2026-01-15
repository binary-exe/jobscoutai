"""
Apply Pack generation service.

Generates tailored resume content, cover note, and ATS checklist.
"""

from typing import Dict, List, Optional, Any
import re

from backend.app.core.config import get_settings


async def generate_apply_pack(
    resume_text: str,
    resume_analysis: Dict[str, Any],
    job_description: str,
    job_analysis: Dict[str, Any],
    use_ai: bool = True,
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
        return _generate_basic_pack(resume_analysis, job_analysis)
    
    # Use AI for generation
    settings = get_settings()
    if not settings.openai_api_key:
        return _generate_basic_pack(resume_analysis, job_analysis)
    
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
        
        # Generate tailored summary
        summary = await _generate_summary(client, resume_text, job_description, resume_analysis, job_analysis)
        
        # Generate tailored bullets
        bullets = await _generate_bullets(client, resume_analysis, job_analysis)
        
        # Generate cover note
        cover_note = await _generate_cover_note(client, resume_analysis, job_analysis)
        
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
) -> str:
    """Generate tailored professional summary."""
    system_prompt = """You are a career coach helping job seekers tailor their resumes.
Write concise, professional summaries that highlight relevant experience."""
    
    prompt = f"""Write a 2-3 sentence professional summary that matches this resume to this job.

Resume highlights:
- Skills: {', '.join(resume_analysis.get('skills', [])[:10])}
- Seniority: {resume_analysis.get('seniority', 'mid')}
- Key achievements: {len(resume_analysis.get('bullets', []))} quantified results

Job requirements:
- Must-haves: {', '.join(job_analysis.get('must_haves', [])[:5])}
- Keywords: {', '.join(job_analysis.get('keywords', [])[:10])}

Write a summary that:
1. Highlights relevant experience and skills
2. Mentions key achievements if relevant
3. Shows alignment with job requirements
4. Is specific and avoids generic phrases

Summary:"""
    
    response = await client.complete(prompt, system_prompt=system_prompt)
    if response.ok:
        return response.content.strip()
    return "Experienced professional with relevant skills and proven track record."


async def _generate_bullets(
    client,
    resume_analysis: Dict,
    job_analysis: Dict,
) -> List[Dict[str, Any]]:
    """Generate tailored resume bullets."""
    system_prompt = """You are a resume writer. Rewrite achievement bullets to match job requirements.
Include quantified metrics and impact."""
    
    existing_bullets = resume_analysis.get('bullets', [])[:5]
    if not existing_bullets:
        return []
    
    bullets_text = "\n".join([f"- {b.get('text', '')}" for b in existing_bullets])
    
    prompt = f"""Rewrite these resume bullets to better match this job. Keep the core achievements but emphasize relevant skills and impact.

Job keywords: {', '.join(job_analysis.get('keywords', [])[:15])}
Job must-haves: {', '.join(job_analysis.get('must_haves', [])[:5])}

Current bullets:
{bullets_text}

Return JSON array of rewritten bullets:
[
  {{"text": "Rewritten bullet point", "match_score": 85}},
  ...
]

Each bullet should:
- Keep original metrics/numbers
- Emphasize skills mentioned in job
- Be specific and action-oriented
- Have a match_score (0-100) indicating relevance"""
    
    response = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
    
    if response.ok and response.json_data:
        bullets = response.json_data
        if isinstance(bullets, list):
            return bullets[:5]
    
    # Fallback: return original bullets with basic scores
    return [
        {"text": b.get("text", ""), "match_score": 70}
        for b in existing_bullets
    ]


async def _generate_cover_note(
    client,
    resume_analysis: Dict,
    job_analysis: Dict,
) -> str:
    """Generate short cover note."""
    system_prompt = """You are a career coach. Write brief, professional cover notes."""
    
    prompt = f"""Write a 2-3 sentence cover note for this job application.

Resume highlights:
- Skills: {', '.join(resume_analysis.get('skills', [])[:8])}
- Seniority: {resume_analysis.get('seniority', 'mid')}

Job focus: {job_analysis.get('rubric', '')[:200]}

Write a brief note that:
1. Expresses interest
2. Highlights 1-2 most relevant skills/experiences
3. Is concise and professional

Cover note:"""
    
    response = await client.complete(prompt, system_prompt=system_prompt)
    if response.ok:
        return response.content.strip()
    return "I am excited to apply for this position and believe my experience aligns well with your requirements."


def _calculate_ats_checklist(
    resume_analysis: Dict,
    job_analysis: Dict,
) -> Dict[str, Any]:
    """Calculate ATS keyword coverage and missing skills."""
    resume_skills = set(s.lower() for s in resume_analysis.get('skills', []))
    job_keywords = set(k.lower() for k in job_analysis.get('keywords', []))
    job_must_haves = set(m.lower() for m in job_analysis.get('must_haves', []))
    
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
) -> Dict[str, Any]:
    """Generate basic pack without AI."""
    skills = resume_analysis.get('skills', [])[:10]
    bullets = resume_analysis.get('bullets', [])[:3]
    
    summary = f"Experienced {resume_analysis.get('seniority', 'professional')} with expertise in {', '.join(skills[:5])}."
    
    tailored_bullets = [
        {"text": b.get("text", ""), "match_score": 60}
        for b in bullets
    ]
    
    cover_note = f"I am interested in this position and believe my experience with {', '.join(skills[:3])} aligns with your requirements."
    
    ats_checklist = _calculate_ats_checklist(resume_analysis, job_analysis)
    
    return {
        "tailored_summary": summary,
        "tailored_bullets": tailored_bullets,
        "cover_note": cover_note,
        "ats_checklist": ats_checklist,
        "keyword_coverage": ats_checklist["keyword_coverage"],
    }
