"""
Learning summary builder for application feedback.

Aggregates feedback to identify patterns and improve future Apply Pack personalization.
"""

from typing import Dict, Any
from collections import Counter
import json
from uuid import UUID
from datetime import datetime, timezone

from backend.app.core.database import db
from backend.app.storage import apply_storage


async def build_learning_summary(user_id: UUID, limit: int = 50) -> Dict[str, Any]:
    """
    Build a learning summary from user's application feedback.
    
    Returns:
        {
            "top_skills_gaps": List[str],  # Most common missing skills
            "recurring_issues": List[str],  # Common rejection reasons
            "positive_signals": List[str],  # Skills/patterns that led to success
            "recommendations": List[str],  # Actionable recommendations
        }
    """
    async with db.connection() as conn:
        # Get recent feedback
        feedback_list = await apply_storage.get_user_feedback_summary(conn, user_id, limit=limit)
        
        if not feedback_list:
            return {
                "top_skills_gaps": [],
                "recurring_issues": [],
                "positive_signals": [],
                "recommendations": [],
            }
        
        # Aggregate data with simple recency weighting
        skills_gaps_w: Dict[str, float] = {}
        rejection_reasons_w: Dict[str, float] = {}
        positive_signals_w: Dict[str, float] = {}

        for fb in feedback_list:
            created_at = fb.get("created_at")
            weight = 1.0
            try:
                if isinstance(created_at, datetime):
                    age_days = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).days
                    weight = 1.0 / (1.0 + (age_days / 30.0))
            except Exception:
                weight = 1.0

            parsed_json = fb.get("parsed_json")
            if isinstance(parsed_json, str):
                try:
                    parsed_json = json.loads(parsed_json)
                except Exception:
                    parsed_json = {}
            elif parsed_json is None:
                parsed_json = {}

            feedback_type = fb.get("feedback_type", "")

            reason_categories = parsed_json.get("reason_categories", [])
            if feedback_type == "rejection":
                for r in reason_categories:
                    rejection_reasons_w[r] = rejection_reasons_w.get(r, 0.0) + weight

                signals = parsed_json.get("signals", [])
                for s in signals:
                    skills_gaps_w[s] = skills_gaps_w.get(s, 0.0) + weight

            elif feedback_type in ["shortlisted", "offer"]:
                signals = parsed_json.get("signals", [])
                for s in signals:
                    positive_signals_w[s] = positive_signals_w.get(s, 0.0) + weight

        # Rank by weighted counts
        skills_gap_counter = Counter(skills_gaps_w)
        rejection_reason_counter = Counter(rejection_reasons_w)
        positive_signal_counter = Counter(positive_signals_w)
        
        top_skills_gaps = [skill for skill, _ in skills_gap_counter.most_common(10)]
        recurring_issues = [reason for reason, _ in rejection_reason_counter.most_common(5)]
        top_positive_signals = [signal for signal, _ in positive_signal_counter.most_common(5)]
        
        # Generate recommendations
        recommendations = []
        if "skills_gap" in recurring_issues:
            if top_skills_gaps:
                recommendations.append(f"Consider highlighting or acquiring: {', '.join(top_skills_gaps[:3])}")
        if "seniority" in recurring_issues:
            recommendations.append("Consider applying to roles that match your current seniority level, or highlight leadership experience more prominently")
        if "location" in recurring_issues:
            recommendations.append("Clarify remote work preferences and location requirements in your applications")
        if top_positive_signals:
            recommendations.append(f"Continue emphasizing: {', '.join(top_positive_signals[:3])}")
        
        return {
            "top_skills_gaps": top_skills_gaps,
            "recurring_issues": recurring_issues,
            "positive_signals": top_positive_signals,
            "recommendations": recommendations,
        }
