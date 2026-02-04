"""
Email Service for JobScoutAI

Handles onboarding email sequences and transactional emails.
Uses Resend API for email delivery.

Email Onboarding Sequence (5 emails):
1. Welcome + how to create first Apply Pack (immediate)
2. Case study: user who got interview (Day 2)
3. Reminder before hitting 2-pack limit (Day 4)
4. Launch offer reminder (Day 6)
5. Feedback request (Day 10)
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from backend.app.core.config import settings

# Email templates
TEMPLATES = {
    "welcome": {
        "subject": "Welcome to JobScout! Let's get you your first Apply Pack",
        "body": """Hi {name}!

Welcome to JobScout - your AI-powered job application assistant.

You've taken the first step toward smarter job hunting. Here's how to make the most of it:

**🚀 Get Your First Apply Pack (Takes 2 Minutes)**
1. Go to the Apply Workspace: {site_url}/apply
2. Paste a job URL or description
3. Upload or paste your resume
4. Click "Generate Apply Pack"

**What You'll Get:**
- Tailored cover letter aligned with the job
- Resume bullet points to highlight
- Trust Report to verify the job is legit
- ATS keyword analysis

**Your Free Trial:**
- 2 Apply Packs per month
- Track up to 5 applications
- Trust Reports on every job

Ready to land your next role faster?

{site_url}/apply

Best,
The JobScout Team
""",
    },
    "case_study": {
        "subject": "How Sarah landed 3 interviews in one week",
        "body": """Hi {name}!

Quick story that might inspire you:

Sarah was applying to 20+ jobs a week but hearing crickets. She was spending hours tailoring each application... and getting nowhere.

Then she tried JobScout.

**The Results:**
- Generated 15 Apply Packs in one afternoon
- Each application was tailored in under 2 minutes
- Trust Reports helped her avoid 4 ghost job postings
- Landed 3 interviews that week

**Her secret?** Instead of spending 45 minutes per application, she focused on applying to MORE of the RIGHT jobs.

The Trust Report feature flagged suspicious postings before she wasted time, and the AI-tailored cover letters actually got read by recruiters.

Ready to speed up your job search?

{site_url}/apply

Best,
The JobScout Team

P.S. Sarah is now a Product Manager at a Series B startup. Your story could be next.
""",
    },
    "quota_reminder": {
        "subject": "You're close to your monthly limit",
        "body": """Hi {name}!

Quick heads up - you've used {used} of your {limit} free Apply Packs this month.

If you're actively job hunting, you might want more firepower. Pro users get:

**Pro Plan (€9/month):**
- 30 Apply Packs per month
- Unlimited application tracking
- DOCX export for ATS compatibility
- Priority generation queue

**Limited Time:** Use code EARLY30 for 30% off your first month.

Upgrade now: {site_url}/pricing

Or, invite friends to get free packs! You both get 10 packs when they create their first Apply Pack.

{site_url}/account

Best,
The JobScout Team
""",
    },
    "launch_offer": {
        "subject": "🎉 Early Bird Special: Save 30% on Pro",
        "body": """Hi {name}!

Hope your job search is going well! I wanted to share a special offer we're running for early users.

**Founder's Deal: €59/year (normally €108)**

That's Pro features for a full year at 45% off:
- 30 Apply Packs every month
- Unlimited application tracking
- DOCX exports for any ATS
- Priority queue

This deal expires {expiry_date}, and we won't run it again.

Claim your spot: {site_url}/pricing?deal=founders

Best,
The JobScout Team

P.S. Already landing interviews? Reply to this email - I'd love to hear your story!
""",
    },
    "feedback_request": {
        "subject": "Quick question about your experience",
        "body": """Hi {name}!

You've been using JobScout for about a week now, and I'd love your honest feedback.

**3 Quick Questions:**
1. What's working well for you?
2. What's frustrating or confusing?
3. What feature would make JobScout 10x more useful?

Just reply to this email - I read every response personally.

Your feedback directly shapes what we build next. Our most popular features came from user suggestions.

Thanks for being an early user!

Best,
{sender_name}
Founder, JobScout
""",
    },
}


class EmailService:
    def __init__(self):
        self.api_key = os.getenv("RESEND_API_KEY")
        self.from_email = os.getenv("EMAIL_FROM", "JobScout <hello@jobscoutai.com>")
        self.site_url = os.getenv("SITE_URL", "https://jobscoutai.vercel.app")
        self.api_url = "https://api.resend.com/emails"
        
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an email via Resend API."""
        if not self.is_configured():
            return {"success": False, "error": "Email service not configured"}
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        
        if reply_to:
            payload["reply_to"] = reply_to
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=10.0,
                )
                
                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": response.text}
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    def render_template(
        self,
        template_key: str,
        **kwargs
    ) -> tuple[str, str]:
        """Render an email template with variables."""
        template = TEMPLATES.get(template_key)
        if not template:
            raise ValueError(f"Unknown template: {template_key}")
        
        # Default variables
        kwargs.setdefault("site_url", self.site_url)
        kwargs.setdefault("sender_name", "Abdul")
        
        subject = template["subject"].format(**kwargs)
        body = template["body"].format(**kwargs)
        
        return subject, body
    
    async def send_welcome_email(self, to_email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Send welcome email (Email 1)."""
        name = name or to_email.split("@")[0]
        subject, body = self.render_template("welcome", name=name)
        return await self.send_email(to_email, subject, body)
    
    async def send_case_study_email(self, to_email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Send case study email (Email 2)."""
        name = name or to_email.split("@")[0]
        subject, body = self.render_template("case_study", name=name)
        return await self.send_email(to_email, subject, body)
    
    async def send_quota_reminder_email(
        self,
        to_email: str,
        used: int,
        limit: int,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send quota reminder email (Email 3)."""
        name = name or to_email.split("@")[0]
        subject, body = self.render_template(
            "quota_reminder",
            name=name,
            used=used,
            limit=limit,
        )
        return await self.send_email(to_email, subject, body)
    
    async def send_launch_offer_email(
        self,
        to_email: str,
        name: Optional[str] = None,
        expiry_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send launch offer email (Email 4)."""
        name = name or to_email.split("@")[0]
        expiry = expiry_date or (datetime.utcnow() + timedelta(days=7)).strftime("%B %d")
        subject, body = self.render_template(
            "launch_offer",
            name=name,
            expiry_date=expiry,
        )
        return await self.send_email(to_email, subject, body)
    
    async def send_feedback_request_email(self, to_email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Send feedback request email (Email 5)."""
        name = name or to_email.split("@")[0]
        subject, body = self.render_template("feedback_request", name=name)
        return await self.send_email(to_email, subject, body, reply_to="abdul@jobscoutai.com")


# Singleton instance
email_service = EmailService()


# Email schedule for onboarding sequence
ONBOARDING_SCHEDULE = [
    {"email": "welcome", "delay_hours": 0},       # Immediate
    {"email": "case_study", "delay_hours": 48},   # Day 2
    {"email": "quota_reminder", "delay_hours": 96},  # Day 4
    {"email": "launch_offer", "delay_hours": 144},   # Day 6
    {"email": "feedback_request", "delay_hours": 240},  # Day 10
]
