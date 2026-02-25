"""
Resume analysis service for Apply Workspace.

Extracts skills, seniority, and evidence bullets from resume text.
"""

from typing import Dict, List, Optional, Any
import json

from backend.app.core.config import get_settings


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


def _clean_skills_list(skills: Any, max_items: int = 30) -> List[str]:
    out: List[str] = []
    seen = set()
    for s in (skills or []):
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


async def analyze_resume(resume_text: str, use_ai: bool = True) -> Dict[str, Any]:
    """
    Analyze resume and extract structured data.
    
    Returns:
        {
            "skills": List[str],
            "seniority": str,  # "entry", "mid", "senior", "lead", "executive"
            "bullets": List[Dict],  # [{"text": "...", "impact": "...", "metrics": [...]}]
        }
    """
    if not use_ai:
        # Basic heuristic extraction
        return _extract_resume_heuristic(resume_text)
    
    # Use AI for structured extraction
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("AI resume analysis is unavailable: OpenAI key is not configured.")
    
    try:
        from jobscout.llm.provider import LLMConfig, get_llm_client
        
        llm_config = LLMConfig(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=2000,
            temperature=0.1,
        )
        
        client = get_llm_client(llm_config)
        if not client:
            raise RuntimeError("AI resume analysis is unavailable: LLM client initialization failed.")
        
        # Create prompt for structured extraction
        system_prompt = """You are a resume analysis expert. Extract structured information from resumes.
Return valid JSON only."""
        
        prompt = f"""Analyze this resume and extract:
1. Technical and professional skills (list as array)
2. Seniority level (one of: entry, mid, senior, lead, executive)
3. Key achievement bullets with quantified impact (array of objects with "text", "impact", "metrics")

Resume text:
{resume_text[:3000]}

Return JSON in this format:
{{
  "skills": ["skill1", "skill2", ...],
  "seniority": "senior",
  "bullets": [
    {{
      "text": "Full bullet point text",
      "impact": "Brief impact description",
      "metrics": ["metric1", "metric2"]
    }}
  ]
}}"""
        
        response = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
        
        if response.ok and response.json_data:
            skills = _clean_skills_list(response.json_data.get("skills", []), 30)
            return {
                "skills": skills,
                "seniority": response.json_data.get("seniority", "mid"),
                "bullets": response.json_data.get("bullets", []),
            }
        
        raise RuntimeError(response.error or "AI resume analysis returned no structured data.")
        
    except Exception as e:
        print(f"Error in AI resume analysis: {e}")
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"AI resume analysis failed: {str(e)}")


def _extract_resume_heuristic(resume_text: str) -> Dict[str, Any]:
    """Basic heuristic extraction without AI."""
    import re
    
    # Extract skills (look for common patterns)
    skills = []
    skill_keywords = [
        "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "sql", "postgresql", "mongodb", "redis", "elasticsearch",
        "git", "ci/cd", "jenkins", "github actions",
        "agile", "scrum", "kanban",
    ]
    
    text_lower = resume_text.lower()
    for skill in skill_keywords:
        if skill in text_lower:
            skills.append(skill.title())
    
    # Determine seniority (heuristic based on keywords)
    seniority = "mid"
    if any(word in text_lower for word in ["intern", "junior", "entry level", "graduate"]):
        seniority = "entry"
    elif any(word in text_lower for word in ["senior", "sr.", "lead", "principal", "architect"]):
        seniority = "senior"
    elif any(word in text_lower for word in ["director", "vp", "vice president", "cto", "cfo", "ceo"]):
        seniority = "executive"
    
    # Extract bullets (look for bullet points with numbers/percentages)
    bullets = []
    lines = resume_text.split("\n")
    for line in lines:
        line = line.strip()
        # Look for bullets with metrics
        if re.search(r'(\d+%|\$\d+|\d+\+|\d+x)', line, re.IGNORECASE):
            # Extract metrics
            metrics = re.findall(r'(\d+%|\$\d+[KMkm]?|\d+\+|\d+x)', line, re.IGNORECASE)
            bullets.append({
                "text": line,
                "impact": "",
                "metrics": metrics[:3],  # Limit to 3 metrics
            })
            if len(bullets) >= 5:  # Limit to 5 bullets
                break
    
    return {
        "skills": _clean_skills_list(skills[:50], 20),  # Limit to 20 skills
        "seniority": seniority,
        "bullets": bullets,
    }
