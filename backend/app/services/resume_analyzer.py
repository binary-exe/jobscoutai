"""
Resume analysis service for Apply Workspace.

Extracts skills, seniority, and evidence bullets from resume text.
"""

from typing import Dict, List, Optional, Any
import json

from backend.app.core.config import get_settings


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
        # Fallback to heuristic if AI not configured
        return _extract_resume_heuristic(resume_text)
    
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
            return _extract_resume_heuristic(resume_text)
        
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
            return {
                "skills": response.json_data.get("skills", []),
                "seniority": response.json_data.get("seniority", "mid"),
                "bullets": response.json_data.get("bullets", []),
            }
        
        # Fallback to heuristic
        return _extract_resume_heuristic(resume_text)
        
    except Exception as e:
        print(f"Error in AI resume analysis: {e}")
        return _extract_resume_heuristic(resume_text)


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
        "skills": skills[:20],  # Limit to 20 skills
        "seniority": seniority,
        "bullets": bullets,
    }
