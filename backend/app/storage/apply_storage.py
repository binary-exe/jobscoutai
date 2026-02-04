"""
Storage functions for Apply Workspace V1.

Handles users, resumes, job targets, trust reports, apply packs, applications, and usage tracking.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
import hashlib
import json

import asyncpg


# ==================== Users ====================

async def get_or_create_user(conn: asyncpg.Connection, email: Optional[str] = None) -> Dict[str, Any]:
    """Get or create a user. For now, we use anonymous users (no email required)."""
    if email:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email
        )
        if row:
            return dict(row)
    
    # Create anonymous user
    user_id = uuid4()
    row = await conn.fetchrow(
        """
        INSERT INTO users (user_id, plan) 
        VALUES ($1, 'free')
        RETURNING *
        """,
        user_id
    )
    return dict(row)


async def get_user(conn: asyncpg.Connection, user_id: UUID) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    row = await conn.fetchrow(
        "SELECT * FROM users WHERE user_id = $1",
        user_id
    )
    return dict(row) if row else None


async def update_user_plan(
    conn: asyncpg.Connection,
    user_id: UUID,
    plan: str,
    subscription_id: Optional[str] = None,
    paddle_customer_id: Optional[str] = None,
    subscription_status: Optional[str] = None,
    subscription_ends_at: Optional[datetime] = None,
) -> None:
    """Update user's plan and subscription info."""
    await conn.execute(
        """
        UPDATE users 
        SET plan = $2, subscription_id = $3, paddle_customer_id = $4,
            subscription_status = $5, subscription_ends_at = $6, updated_at = NOW()
        WHERE user_id = $1
        """,
        user_id, plan, subscription_id, paddle_customer_id, subscription_status, subscription_ends_at
    )


# ==================== User Profiles ====================

async def get_user_profile(conn: asyncpg.Connection, user_id: UUID) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow("SELECT * FROM user_profiles WHERE user_id = $1", user_id)
    return dict(row) if row else None


async def upsert_user_profile(conn: asyncpg.Connection, user_id: UUID, profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert user profile. Expects keys aligned to user_profiles columns.
    JSON fields should be python dict/list; arrays should be python lists.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO user_profiles (
            user_id, headline, location, desired_roles, work_authorization, remote_preferences,
            salary_expectations, skills, education, certifications, projects, interests, links,
            primary_resume_id, profile_hash
        )
        VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11, $12, $13,
            $14, $15
        )
        ON CONFLICT (user_id) DO UPDATE SET
            headline = EXCLUDED.headline,
            location = EXCLUDED.location,
            desired_roles = EXCLUDED.desired_roles,
            work_authorization = EXCLUDED.work_authorization,
            remote_preferences = EXCLUDED.remote_preferences,
            salary_expectations = EXCLUDED.salary_expectations,
            skills = EXCLUDED.skills,
            education = EXCLUDED.education,
            certifications = EXCLUDED.certifications,
            projects = EXCLUDED.projects,
            interests = EXCLUDED.interests,
            links = EXCLUDED.links,
            primary_resume_id = COALESCE(EXCLUDED.primary_resume_id, user_profiles.primary_resume_id),
            profile_hash = EXCLUDED.profile_hash,
            updated_at = NOW()
        RETURNING *
        """,
        user_id,
        profile.get("headline"),
        profile.get("location"),
        profile.get("desired_roles") or [],
        profile.get("work_authorization"),
        profile.get("remote_preferences"),
        json.dumps(profile.get("salary_expectations")) if profile.get("salary_expectations") is not None else None,
        profile.get("skills") or [],
        json.dumps(profile.get("education")) if profile.get("education") is not None else None,
        profile.get("certifications") or [],
        json.dumps(profile.get("projects")) if profile.get("projects") is not None else None,
        profile.get("interests") or [],
        json.dumps(profile.get("links")) if profile.get("links") is not None else None,
        profile.get("primary_resume_id"),
        profile.get("profile_hash"),
    )
    return dict(row)


# ==================== Resume Versions ====================

def hash_resume(text: str) -> str:
    """Generate SHA256 hash of resume text."""
    return hashlib.sha256(text.encode()).hexdigest()


async def create_resume_version(
    conn: asyncpg.Connection,
    user_id: UUID,
    resume_text: str,
    proof_points: Optional[str] = None,
    extracted_skills: Optional[Dict] = None,
    extracted_seniority: Optional[str] = None,
    extracted_bullets: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Create a new resume version."""
    resume_hash = hash_resume(resume_text)
    resume_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO resume_versions 
        (resume_id, user_id, resume_text, resume_hash, proof_points, 
         extracted_skills, extracted_seniority, extracted_bullets)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        resume_id, user_id, resume_text, resume_hash, proof_points,
        json.dumps(extracted_skills) if extracted_skills else None,
        extracted_seniority,
        json.dumps(extracted_bullets) if extracted_bullets else None,
    )
    return dict(row)


async def get_resume_by_hash(conn: asyncpg.Connection, user_id: UUID, resume_hash: str) -> Optional[Dict[str, Any]]:
    """Get resume by hash for a user (for caching)."""
    row = await conn.fetchrow(
        """
        SELECT *
        FROM resume_versions
        WHERE user_id = $1 AND resume_hash = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
        resume_hash,
    )
    return dict(row) if row else None


async def list_resume_versions(conn: asyncpg.Connection, user_id: UUID, limit: int = 25) -> List[Dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT resume_id, user_id, resume_hash, created_at, updated_at, extracted_seniority, extracted_skills
        FROM resume_versions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id, limit
    )
    return [dict(r) for r in rows]


async def get_resume_version(conn: asyncpg.Connection, user_id: UUID, resume_id: UUID) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        "SELECT * FROM resume_versions WHERE user_id = $1 AND resume_id = $2",
        user_id, resume_id
    )
    return dict(row) if row else None


async def set_primary_resume(conn: asyncpg.Connection, user_id: UUID, resume_id: UUID) -> Dict[str, Any]:
    row = await conn.fetchrow(
        """
        INSERT INTO user_profiles (user_id, primary_resume_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO UPDATE SET
            primary_resume_id = EXCLUDED.primary_resume_id,
            updated_at = NOW()
        RETURNING *
        """,
        user_id, resume_id
    )
    return dict(row)


# ==================== Job Targets ====================

def hash_job_target(url: Optional[str], text: Optional[str]) -> str:
    """Generate SHA256 hash of job target (URL or text)."""
    content = (url or "") + (text or "")
    return hashlib.sha256(content.encode()).hexdigest()


async def create_job_target(
    conn: asyncpg.Connection,
    user_id: Optional[UUID],
    job_url: Optional[str],
    job_text: Optional[str],
    extracted_json: Optional[Dict] = None,
    title: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    remote_type: Optional[str] = None,
    employment_type: Optional[str] = None,
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    salary_currency: Optional[str] = None,
    description_text: Optional[str] = None,
    requirements: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    must_haves: Optional[List[str]] = None,
    role_rubric: Optional[str] = None,
    html: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new job target."""
    job_hash = hash_job_target(job_url, job_text)
    job_target_id = uuid4()
    
    # Limit HTML size to prevent database bloat (max 500KB)
    if html and len(html) > 500000:
        html = html[:500000] + "... [truncated]"
    
    row = await conn.fetchrow(
        """
        INSERT INTO job_targets 
        (job_target_id, user_id, job_url, job_text, job_hash, extracted_json,
         title, company, location, remote_type, employment_type,
         salary_min, salary_max, salary_currency, description_text,
         requirements, keywords, must_haves, role_rubric, html)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        RETURNING *
        """,
        job_target_id, user_id, job_url, job_text, job_hash,
        json.dumps(extracted_json) if extracted_json else None,
        title, company, location, remote_type, employment_type,
        salary_min, salary_max, salary_currency, description_text,
        requirements, keywords, must_haves, role_rubric, html,
    )
    return dict(row)


async def get_job_target_by_hash(conn: asyncpg.Connection, job_hash: str) -> Optional[Dict[str, Any]]:
    """Get job target by hash (for caching)."""
    row = await conn.fetchrow(
        "SELECT * FROM job_targets WHERE job_hash = $1 ORDER BY created_at DESC LIMIT 1",
        job_hash
    )
    return dict(row) if row else None


# ==================== Trust Reports ====================

async def create_trust_report(
    conn: asyncpg.Connection,
    job_target_id: UUID,
    scam_risk: str,
    scam_reasons: List[str],
    ghost_likelihood: str,
    ghost_reasons: List[str],
    staleness_score: Optional[int] = None,
    staleness_reasons: Optional[List[str]] = None,
    domain: Optional[str] = None,
    extracted_emails: Optional[List[str]] = None,
    extracted_phones: Optional[List[str]] = None,
    apply_link_status: Optional[str] = None,
    scam_score: Optional[int] = None,
    ghost_score: Optional[int] = None,
    domain_consistency_reasons: Optional[List[str]] = None,
    trust_score: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a trust report for a job target."""
    trust_report_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO trust_reports 
        (trust_report_id, job_target_id, scam_risk, scam_reasons, scam_score,
         ghost_likelihood, ghost_reasons, ghost_score,
         staleness_score, staleness_reasons, domain, 
         extracted_emails, extracted_phones, apply_link_status,
         domain_consistency_reasons, trust_score)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        RETURNING *
        """,
        trust_report_id, job_target_id, scam_risk, scam_reasons, scam_score,
        ghost_likelihood, ghost_reasons, ghost_score,
        staleness_score, staleness_reasons, domain,
        extracted_emails, extracted_phones, apply_link_status,
        domain_consistency_reasons, trust_score,
    )
    return dict(row)


async def get_trust_report(conn: asyncpg.Connection, job_target_id: UUID) -> Optional[Dict[str, Any]]:
    """Get trust report for a job target."""
    row = await conn.fetchrow(
        "SELECT * FROM trust_reports WHERE job_target_id = $1 ORDER BY created_at DESC LIMIT 1",
        job_target_id
    )
    return dict(row) if row else None


# ==================== Apply Packs ====================

def hash_apply_pack(resume_hash: str, job_hash: str) -> str:
    """Generate hash for apply pack (resume + job combination)."""
    return hashlib.sha256(f"{resume_hash}:{job_hash}".encode()).hexdigest()


async def create_apply_pack(
    conn: asyncpg.Connection,
    user_id: UUID,
    resume_id: UUID,
    job_target_id: UUID,
    pack_hash: str,
    tailored_summary: Optional[str] = None,
    tailored_bullets: Optional[List[Dict]] = None,
    cover_note: Optional[str] = None,
    ats_checklist: Optional[Dict] = None,
    keyword_coverage: Optional[float] = None,
) -> Dict[str, Any]:
    """Create an apply pack."""
    apply_pack_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO apply_packs 
        (apply_pack_id, user_id, resume_id, job_target_id, pack_hash,
         tailored_summary, tailored_bullets, cover_note, ats_checklist, keyword_coverage)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        apply_pack_id, user_id, resume_id, job_target_id, pack_hash,
        tailored_summary,
        json.dumps(tailored_bullets) if tailored_bullets else None,
        cover_note,
        json.dumps(ats_checklist) if ats_checklist else None,
        keyword_coverage,
    )
    return dict(row)


async def get_apply_pack_by_hash(conn: asyncpg.Connection, user_id: UUID, pack_hash: str) -> Optional[Dict[str, Any]]:
    """Get apply pack by hash for a user (for caching)."""
    row = await conn.fetchrow(
        """
        SELECT *
        FROM apply_packs
        WHERE user_id = $1 AND pack_hash = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        user_id,
        pack_hash,
    )
    return dict(row) if row else None


async def get_user_apply_packs(
    conn: asyncpg.Connection,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get user's apply packs."""
    rows = await conn.fetch(
        """
        SELECT ap.*, jt.title, jt.company, jt.job_url
        FROM apply_packs ap
        LEFT JOIN job_targets jt ON ap.job_target_id = jt.job_target_id
        WHERE ap.user_id = $1
        ORDER BY ap.created_at DESC
        LIMIT $2 OFFSET $3
        """,
        user_id, limit, offset
    )
    return [dict(row) for row in rows]


# ==================== Applications (Tracker) ====================

async def create_application(
    conn: asyncpg.Connection,
    user_id: UUID,
    apply_pack_id: Optional[UUID],
    job_target_id: Optional[UUID],
    status: str = "applied",
    notes: Optional[str] = None,
    reminder_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Create a tracked application."""
    application_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO applications 
        (application_id, user_id, apply_pack_id, job_target_id, status, notes, reminder_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        application_id, user_id, apply_pack_id, job_target_id, status, notes, reminder_at,
    )
    return dict(row)


async def get_user_applications(
    conn: asyncpg.Connection,
    user_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Get user's applications."""
    if status:
        rows = await conn.fetch(
            """
            SELECT a.*, jt.title, jt.company, jt.job_url
            FROM applications a
            LEFT JOIN job_targets jt ON a.job_target_id = jt.job_target_id
            WHERE a.user_id = $1 AND a.status = $2
            ORDER BY a.applied_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id, status, limit, offset
        )
    else:
        rows = await conn.fetch(
            """
            SELECT a.*, jt.title, jt.company, jt.job_url
            FROM applications a
            LEFT JOIN job_targets jt ON a.job_target_id = jt.job_target_id
            WHERE a.user_id = $1
            ORDER BY a.applied_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )
    return [dict(row) for row in rows]


# ==================== Application Feedback ====================

async def create_application_feedback(
    conn: asyncpg.Connection,
    application_id: UUID,
    feedback_type: str,
    raw_text: Optional[str] = None,
    parsed_json: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Create application feedback record."""
    feedback_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO application_feedback 
        (feedback_id, application_id, feedback_type, raw_text, parsed_json)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        feedback_id, application_id, feedback_type, raw_text,
        json.dumps(parsed_json) if parsed_json else None,
    )
    return dict(row)


async def get_application_feedback(
    conn: asyncpg.Connection,
    application_id: UUID,
) -> List[Dict[str, Any]]:
    """Get all feedback for an application."""
    rows = await conn.fetch(
        """
        SELECT * FROM application_feedback
        WHERE application_id = $1
        ORDER BY created_at DESC
        """,
        application_id
    )
    return [dict(row) for row in rows]


async def get_user_feedback_summary(
    conn: asyncpg.Connection,
    user_id: UUID,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get aggregated feedback for learning summary."""
    rows = await conn.fetch(
        """
        SELECT af.*, a.user_id
        FROM application_feedback af
        JOIN applications a ON af.application_id = a.application_id
        WHERE a.user_id = $1
        ORDER BY af.created_at DESC
        LIMIT $2
        """,
        user_id, limit
    )
    return [dict(row) for row in rows]


# ==================== Usage Ledger ====================

async def record_usage(
    conn: asyncpg.Connection,
    user_id: UUID,
    action_type: str,
    apply_pack_id: Optional[UUID] = None,
) -> None:
    """Record a usage event."""
    usage_id = uuid4()
    await conn.execute(
        """
        INSERT INTO usage_ledger (usage_id, user_id, action_type, apply_pack_id)
        VALUES ($1, $2, $3, $4)
        """,
        usage_id, user_id, action_type, apply_pack_id
    )


async def get_user_usage_count(
    conn: asyncpg.Connection,
    user_id: UUID,
    action_type: str,
    month: Optional[datetime] = None,
) -> int:
    """Get user's usage count for a given action type in a month."""
    if month:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM usage_ledger
            WHERE user_id = $1 
              AND action_type = $2
              AND date_trunc('month', created_at) = date_trunc('month', $3::timestamptz)
            """,
            user_id, action_type, month
        )
    else:
        # Current month
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count
            FROM usage_ledger
            WHERE user_id = $1 
              AND action_type = $2
              AND date_trunc('month', created_at) = date_trunc('month', NOW())
            """,
            user_id, action_type
        )
    return row["count"] if row else 0


async def check_user_quota(
    conn: asyncpg.Connection,
    user_id: UUID,
    action_type: str,
) -> Dict[str, Any]:
    """
    Check if user has quota remaining for an action.
    
    Tiered pricing:
    - free: 2 apply packs/month, 5 tracked apps, no DOCX
    - pro: 30 apply packs/month, unlimited tracking, DOCX export (€9/month)
    - pro_plus: 100 apply packs/month, everything in pro + priority (€19/month)
    - annual: Same as pro but yearly billing (€79/year)
    
    Pack top-ups add to base quota without changing plan.
    """
    user = await get_user(conn, user_id)
    if not user:
        return {"allowed": False, "reason": "User not found"}
    
    plan = user.get("plan", "free")
    
    # Check subscription status for paid plans
    subscription_status = user.get("subscription_status")
    paid_plans = ("pro", "pro_plus", "annual", "paid")  # Include legacy "paid" for backwards compat
    if plan in paid_plans and subscription_status not in ("active", "past_due", None):
        # Subscription cancelled or expired - revert to free limits
        plan = "free"
    
    # Define quotas per plan
    quotas = {
        "free": {
            "apply_pack": 2,
            "docx_export": 0,  # Not allowed on free
            "tracking": 5,  # 5 active applications for free users
            "trust_report": None,  # Unlimited
        },
        "pro": {
            "apply_pack": 30,
            "docx_export": None,  # Unlimited
            "tracking": None,  # Unlimited
            "trust_report": None,  # Unlimited
        },
        "pro_plus": {
            "apply_pack": 100,
            "docx_export": None,  # Unlimited
            "tracking": None,  # Unlimited
            "trust_report": None,  # Unlimited
        },
        "annual": {
            "apply_pack": 30,  # Same as pro
            "docx_export": None,  # Unlimited
            "tracking": None,  # Unlimited
            "trust_report": None,  # Unlimited
        },
        # Legacy support
        "paid": {
            "apply_pack": 30,
            "docx_export": None,
            "tracking": None,
            "trust_report": None,
        },
    }
    
    quota = quotas.get(plan, quotas["free"]).get(action_type)
    
    if quota is None:
        # Unlimited
        return {"allowed": True, "remaining": None, "limit": None}
    
    if quota == 0:
        # Not allowed at all for this plan
        return {"allowed": False, "remaining": 0, "limit": 0, "used": 0}
    
    # Add pack top-ups for apply_pack
    if action_type == "apply_pack":
        topup_count = await get_pack_topups(conn, user_id)
        quota += topup_count
    
    # Special handling for tracking - count active applications instead of usage table
    if action_type == "tracking":
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) as count FROM applications 
            WHERE user_id = $1 AND status NOT IN ('rejected', 'withdrawn', 'offer')
            """,
            user_id
        )
        used = row["count"] if row else 0
    else:
        used = await get_user_usage_count(conn, user_id, action_type)
    
    remaining = quota - used
    
    return {
        "allowed": remaining > 0,
        "remaining": max(0, remaining),
        "limit": quota,
        "used": used,
    }


async def get_pack_topups(conn: asyncpg.Connection, user_id: UUID) -> int:
    """Get total unused pack top-ups for a user."""
    try:
        row = await conn.fetchrow(
            """
            SELECT COALESCE(SUM(pack_count), 0) as total
            FROM pack_topups
            WHERE user_id = $1 AND (expires_at IS NULL OR expires_at > NOW())
            """,
            user_id
        )
        return row["total"] if row else 0
    except Exception:
        # Table might not exist yet (migration not run)
        return 0


async def add_pack_topup(
    conn: asyncpg.Connection,
    user_id: UUID,
    pack_count: int,
    payment_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add pack top-up for a user."""
    row = await conn.fetchrow(
        """
        INSERT INTO pack_topups (user_id, pack_count, payment_id)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        user_id, pack_count, payment_id
    )
    return dict(row)


# ==================== Referrals ====================

import secrets

def generate_referral_code() -> str:
    """Generate a unique referral code."""
    return secrets.token_urlsafe(8)  # ~11 chars, URL-safe


async def get_or_create_referral_code(conn: asyncpg.Connection, user_id: UUID) -> str:
    """Get user's referral code, creating one if it doesn't exist."""
    try:
        row = await conn.fetchrow(
            "SELECT referral_code FROM users WHERE user_id = $1",
            user_id
        )
        
        if row and row.get("referral_code"):
            return row["referral_code"]
        
        # Generate and save a new code
        code = generate_referral_code()
        try:
            await conn.execute(
                "UPDATE users SET referral_code = $1 WHERE user_id = $2",
                code, user_id
            )
        except Exception:
            # Column might not exist yet
            pass
        return code
    except Exception:
        # Column might not exist yet (migration not run)
        return generate_referral_code()


async def get_user_by_referral_code(conn: asyncpg.Connection, code: str) -> Optional[Dict[str, Any]]:
    """Get user by referral code."""
    try:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE referral_code = $1",
            code
        )
        return dict(row) if row else None
    except Exception:
        # Column might not exist yet (migration not run)
        return None


async def create_referral(
    conn: asyncpg.Connection,
    referrer_id: UUID,
    referral_code: str,
) -> Dict[str, Any]:
    """Create a pending referral record."""
    row = await conn.fetchrow(
        """
        INSERT INTO referrals (referrer_id, referral_code, status)
        VALUES ($1, $2, 'pending')
        RETURNING *
        """,
        referrer_id, referral_code
    )
    return dict(row)


async def complete_referral(
    conn: asyncpg.Connection,
    referral_code: str,
    referee_id: UUID,
) -> Optional[Dict[str, Any]]:
    """
    Complete a referral when referee creates their first Apply Pack.
    Awards packs to both referrer and referee.
    
    Returns the updated referral or None if not found/already completed.
    """
    REFERRAL_PACKS = 10  # Packs awarded to each party
    
    # Find the referrer by code
    referrer = await get_user_by_referral_code(conn, referral_code)
    if not referrer:
        return None
    
    referrer_id = referrer["user_id"]
    
    # Check if this referee already has a completed referral
    existing = await conn.fetchrow(
        """
        SELECT * FROM referrals 
        WHERE referee_id = $1 AND status = 'completed'
        """,
        referee_id
    )
    if existing:
        return None  # Already completed a referral
    
    # Mark user as referred
    await conn.execute(
        "UPDATE users SET referred_by = $1 WHERE user_id = $2 AND referred_by IS NULL",
        referrer_id, referee_id
    )
    
    # Create or update referral record
    row = await conn.fetchrow(
        """
        INSERT INTO referrals (referrer_id, referee_id, referral_code, status, 
                              packs_awarded_referrer, packs_awarded_referee, completed_at)
        VALUES ($1, $2, $3, 'completed', $4, $4, NOW())
        ON CONFLICT (referral_code) DO UPDATE SET
            referee_id = EXCLUDED.referee_id,
            status = 'completed',
            packs_awarded_referrer = $4,
            packs_awarded_referee = $4,
            completed_at = NOW()
        RETURNING *
        """,
        referrer_id, referee_id, referral_code, REFERRAL_PACKS
    )
    
    if row:
        # Award packs to referrer
        await add_pack_topup(conn, referrer_id, REFERRAL_PACKS)
        # Award packs to referee
        await add_pack_topup(conn, referee_id, REFERRAL_PACKS)
    
    return dict(row) if row else None


async def get_user_referral_stats(conn: asyncpg.Connection, user_id: UUID) -> Dict[str, Any]:
    """Get referral statistics for a user."""
    # Get user's referral code
    code = await get_or_create_referral_code(conn, user_id)
    
    # Count completed referrals
    try:
        row = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COALESCE(SUM(packs_awarded_referrer) FILTER (WHERE status = 'completed'), 0) as total_packs_earned
            FROM referrals
            WHERE referrer_id = $1
            """,
            user_id
        )
        
        return {
            "referral_code": code,
            "completed_referrals": row["completed_count"] if row else 0,
            "pending_referrals": row["pending_count"] if row else 0,
            "total_packs_earned": row["total_packs_earned"] if row else 0,
        }
    except Exception:
        # Table might not exist yet (migration not run)
        return {
            "referral_code": code,
            "completed_referrals": 0,
            "pending_referrals": 0,
            "total_packs_earned": 0,
        }
