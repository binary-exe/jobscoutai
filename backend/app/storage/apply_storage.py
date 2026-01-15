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


async def get_resume_by_hash(conn: asyncpg.Connection, resume_hash: str) -> Optional[Dict[str, Any]]:
    """Get resume by hash (for caching)."""
    row = await conn.fetchrow(
        "SELECT * FROM resume_versions WHERE resume_hash = $1 ORDER BY created_at DESC LIMIT 1",
        resume_hash
    )
    return dict(row) if row else None


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
) -> Dict[str, Any]:
    """Create a new job target."""
    job_hash = hash_job_target(job_url, job_text)
    job_target_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO job_targets 
        (job_target_id, user_id, job_url, job_text, job_hash, extracted_json,
         title, company, location, remote_type, employment_type,
         salary_min, salary_max, salary_currency, description_text,
         requirements, keywords, must_haves, role_rubric)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
        RETURNING *
        """,
        job_target_id, user_id, job_url, job_text, job_hash,
        json.dumps(extracted_json) if extracted_json else None,
        title, company, location, remote_type, employment_type,
        salary_min, salary_max, salary_currency, description_text,
        requirements, keywords, must_haves, role_rubric,
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
) -> Dict[str, Any]:
    """Create a trust report for a job target."""
    trust_report_id = uuid4()
    
    row = await conn.fetchrow(
        """
        INSERT INTO trust_reports 
        (trust_report_id, job_target_id, scam_risk, scam_reasons, ghost_likelihood, 
         ghost_reasons, staleness_score, staleness_reasons, domain, 
         extracted_emails, extracted_phones, apply_link_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING *
        """,
        trust_report_id, job_target_id, scam_risk, scam_reasons, ghost_likelihood,
        ghost_reasons, staleness_score, staleness_reasons, domain,
        extracted_emails, extracted_phones, apply_link_status,
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


async def get_apply_pack_by_hash(conn: asyncpg.Connection, pack_hash: str) -> Optional[Dict[str, Any]]:
    """Get apply pack by hash (for caching)."""
    row = await conn.fetchrow(
        "SELECT * FROM apply_packs WHERE pack_hash = $1 ORDER BY created_at DESC LIMIT 1",
        pack_hash
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
    """Check if user has quota remaining for an action."""
    user = await get_user(conn, user_id)
    if not user:
        return {"allowed": False, "reason": "User not found"}
    
    plan = user.get("plan", "free")
    
    # Define quotas
    quotas = {
        "free": {
            "apply_pack": 2,
            "docx_export": 0,  # Not allowed on free
            "trust_report": None,  # Unlimited
        },
        "paid": {
            "apply_pack": 30,
            "docx_export": None,  # Unlimited
            "trust_report": None,  # Unlimited
        },
    }
    
    quota = quotas.get(plan, quotas["free"]).get(action_type)
    
    if quota is None:
        # Unlimited
        return {"allowed": True, "remaining": None, "limit": None}
    
    used = await get_user_usage_count(conn, user_id, action_type)
    remaining = quota - used
    
    return {
        "allowed": remaining > 0,
        "remaining": max(0, remaining),
        "limit": quota,
        "used": used,
    }
