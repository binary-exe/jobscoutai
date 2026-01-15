"""
Job analysis service for Apply Workspace.

Extracts must-haves, keywords, and generates role rubric from job description.
"""

from typing import Dict, List, Optional, Any
import re

from backend.app.core.config import get_settings


async def analyze_job(description_text: str, use_ai: bool = True) -> Dict[str, Any]:
    """
    Analyze job description and extract structured data.
    
    Returns:
        {
            "must_haves": List[str],  # Required skills/qualifications
            "keywords": List[str],  # Important keywords for ATS
            "rubric": str,  # LLM-generated role rubric
        }
    """
    if not use_ai:
        # Basic heuristic extraction
        return _extract_job_heuristic(description_text)
    
    # Use AI for structured extraction
    settings = get_settings()
    if not settings.openai_api_key:
        return _extract_job_heuristic(description_text)
    
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
            return _extract_job_heuristic(description_text)
        
        system_prompt = """You are a job analysis expert. Extract key information from job descriptions.
Return valid JSON only."""
        
        prompt = f"""Analyze this job description and extract:
1. Must-have requirements (required skills, qualifications, experience)
2. Important keywords for ATS matching (technologies, tools, methodologies)
3. A brief role rubric (2-3 sentences describing what success looks like in this role)

Job description:
{description_text[:4000]}

Return JSON in this format:
{{
  "must_haves": ["requirement1", "requirement2", ...],
  "keywords": ["keyword1", "keyword2", ...],
  "rubric": "Brief rubric text"
}}"""
        
        response = await client.complete(prompt, system_prompt=system_prompt, json_mode=True)
        
        if response.ok and response.json_data:
            return {
                "must_haves": response.json_data.get("must_haves", []),
                "keywords": response.json_data.get("keywords", []),
                "rubric": response.json_data.get("rubric", ""),
            }
        
        return _extract_job_heuristic(description_text)
        
    except Exception as e:
        print(f"Error in AI job analysis: {e}")
        return _extract_job_heuristic(description_text)


def _extract_job_heuristic(description_text: str) -> Dict[str, Any]:
    """Basic heuristic extraction without AI."""
    text_lower = description_text.lower()
    
    # Extract must-haves (look for "required", "must have", etc.)
    must_haves = []
    required_section = re.search(r'(required|must have|qualifications?|requirements?)[:.]?\s*(.+?)(?=\n\n|\n[A-Z]|$)', text_lower, re.DOTALL | re.IGNORECASE)
    if required_section:
        required_text = required_section.group(2)
        # Extract bullet points or sentences
        bullets = re.split(r'[•\-\*]\s*|\d+\.\s*', required_text)
        must_haves = [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10][:10]
    
    # Extract keywords (common tech terms)
    keywords = []
    tech_keywords = [
        "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "sql", "postgresql", "mongodb", "redis", "elasticsearch",
        "agile", "scrum", "kanban", "ci/cd", "devops",
        "api", "rest", "graphql", "microservices",
    ]
    
    for keyword in tech_keywords:
        if keyword in text_lower:
            keywords.append(keyword.title())
    
    # Generate basic rubric
    rubric = "Success in this role requires meeting the key requirements and demonstrating relevant experience."
    
    return {
        "must_haves": must_haves[:15],
        "keywords": keywords[:30],
        "rubric": rubric,
    }
