"""
API endpoints for Apply Workspace V1.

Handles job parsing, trust reports, resume processing, and apply pack generation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
import json

from fastapi import APIRouter, HTTPException, Depends, Header, Response, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

from backend.app.core.database import db
from backend.app.core.auth import get_current_user, AuthUser
from backend.app.core.rate_limit import check_rate_limit, apply_pack_limiter, job_capture_limiter
from backend.app.storage import apply_storage
from backend.app.services import job_parser
from backend.app.services import trust_analyzer
from backend.app.services import resume_analyzer
from backend.app.services import resume_parser
from backend.app.services import job_analyzer
from backend.app.services import apply_pack_generator
from backend.app.services import learning_summary

router = APIRouter(prefix="/apply", tags=["apply"])

# python-multipart is required by FastAPI for UploadFile/File(...) endpoints.
# In misconfigured dev environments, FastAPI raises at import time, which prevents the whole API from starting.
# We guard the upload endpoint so the app can still boot and return a clear error message.
try:
    import multipart  # type: ignore  # noqa: F401

    _HAS_MULTIPART = True
except Exception:
    _HAS_MULTIPART = False


# ==================== Request/Response Models ====================

class JobIntakeRequest(BaseModel):
    job_url: Optional[HttpUrl] = None
    job_text: Optional[str] = None


class ResumeIntakeRequest(BaseModel):
    resume_text: str
    proof_points: Optional[str] = None


class GeneratePackRequest(BaseModel):
    resume_text: str
    job_url: Optional[HttpUrl] = None
    job_text: Optional[str] = None
    use_ai: bool = True


class TrustReportResponse(BaseModel):
    trust_report_id: str
    scam_risk: str
    scam_reasons: list[str]
    ghost_likelihood: str
    ghost_reasons: list[str]
    staleness_score: Optional[int] = None
    staleness_reasons: Optional[list[str]] = None
    scam_score: Optional[int] = None
    ghost_score: Optional[int] = None
    apply_link_status: Optional[str] = None
    apply_link_final_url: Optional[str] = None
    apply_link_redirects: Optional[int] = None
    apply_link_cached: Optional[bool] = None
    apply_link_warnings: Optional[list[str]] = None
    domain_consistency_reasons: Optional[list[str]] = None
    trust_score: Optional[int] = None
    verified_at: Optional[datetime] = None
    confidence: Optional[dict] = None
    community: Optional[dict[str, int]] = None
    community_reasons: Optional[list[str]] = None
    next_steps: Optional[list[str]] = None


def _confidence_from_reasons(reasons: Optional[list[str]]) -> int:
    """
    Cheap confidence proxy: more independent signals => higher confidence.
    Returns 0..100.
    """
    if not reasons:
        return 25
    # Down-weight generic "no obvious ..." sentences
    meaningful = [
        r for r in reasons
        if r and "no obvious" not in r.lower() and "no posting date" not in r.lower()
    ]
    n = len(meaningful)
    if n >= 5:
        return 90
    if n >= 3:
        return 75
    if n >= 1:
        return 55
    return 35


def _build_confidence(report: dict) -> dict:
    return {
        "scam": _confidence_from_reasons(report.get("scam_reasons")),
        "ghost": _confidence_from_reasons(report.get("ghost_reasons")),
        "staleness": _confidence_from_reasons(report.get("staleness_reasons")),
        "domain": _confidence_from_reasons(report.get("domain_consistency_reasons")),
        "overall": int(
            (
                _confidence_from_reasons(report.get("scam_reasons"))
                + _confidence_from_reasons(report.get("ghost_reasons"))
                + _confidence_from_reasons(report.get("staleness_reasons"))
                + _confidence_from_reasons(report.get("domain_consistency_reasons"))
            )
            / 4
        ),
    }


def _community_penalty(community: dict[str, int]) -> tuple[int, list[str]]:
    """
    Convert community feedback into a score penalty (0..25) + reasons for UI.
    """
    reports_total = int(community.get("reports_total", 0) or 0)
    inaccurate = int(community.get("inaccurate_total", 0) or 0)
    accurate = int(community.get("accurate_total", 0) or 0)

    penalty = min(25, reports_total * 4 + inaccurate * 6)
    reasons: list[str] = []

    if reports_total > 0:
        reasons.append(f"Community reports: {reports_total}")
    if inaccurate > 0:
        reasons.append(f"Marked inaccurate: {inaccurate}")
    if accurate > 0:
        reasons.append(f"Marked accurate: {accurate}")

    return penalty, reasons


def _link_warnings_from_url(url: Optional[str]) -> list[str]:
    """Cheap link warnings (no network) for cached reports."""
    if not url:
        return []
    try:
        d = trust_analyzer.extract_domain(url)
        if d and hasattr(trust_analyzer, "URL_SHORTENER_DOMAINS") and d in trust_analyzer.URL_SHORTENER_DOMAINS:
            return ["Apply link uses a URL shortener (destination is hidden)"]
    except Exception:
        return []
    return []


def _build_next_steps(report: dict) -> list[str]:
    """
    Turn trust signals into an actionable checklist.

    This intentionally stays heuristic and low-cost: no extra network calls.
    """
    steps: list[str] = []

    scam_risk = (report.get("scam_risk") or "").lower()
    ghost = (report.get("ghost_likelihood") or "").lower()
    staleness_score = report.get("staleness_score")
    apply_link_status = (report.get("apply_link_status") or "").lower()
    trust_score = report.get("trust_score")
    domain_warnings = report.get("domain_consistency_reasons") or []
    link_warnings = report.get("apply_link_warnings") or []

    if scam_risk == "high" or (isinstance(trust_score, int) and trust_score <= 40):
        steps.append("Avoid applying through this link; verify the company and role on the official careers page.")
        steps.append("Do not share sensitive info (passport, bank details) until legitimacy is confirmed.")

    if apply_link_status == "broken":
        steps.append("Apply link looks broken — search the company’s careers site or ATS directly for a live listing.")
    elif apply_link_status == "missing":
        steps.append("No apply link found — search the company’s careers page or the original posting source.")

    if domain_warnings:
        steps.append("Double-check that the company website domain and apply-link domain match before proceeding.")

    if link_warnings:
        steps.append("Be cautious with redirects/shortened links; confirm the final destination is an official ATS/company domain.")

    if isinstance(staleness_score, int) and staleness_score >= 50:
        steps.append("Posting may be stale — prioritize newer listings or reach out via referral before investing time.")

    if ghost == "high":
        steps.append("Ghost-job signals are high — prioritize roles with recent activity or a direct recruiter contact.")

    # Positive action when signals are OK
    if not steps and (scam_risk in ("low", "medium")):
        steps.append("Looks reasonably safe — proceed to apply, then click “Start Tracking” to manage follow-ups.")

    # Always end with a lightweight reminder
    steps.append("If you applied, set a reminder date and track outcomes to improve your targeting over time.")

    # Deduplicate while preserving order
    seen = set()
    deduped: list[str] = []
    for s in steps:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped[:7]


class ApplyPackResponse(BaseModel):
    apply_pack_id: str
    tailored_summary: Optional[str] = None
    tailored_bullets: Optional[list[dict]] = None
    cover_note: Optional[str] = None
    ats_checklist: Optional[dict] = None
    keyword_coverage: Optional[float] = None


class UpdateJobTargetRequest(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None
    employment_type: Optional[list[str]] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    description_text: Optional[str] = None


class ApplicationFeedbackRequest(BaseModel):
    feedback_type: str  # 'rejection', 'shortlisted', 'offer', 'no_response', 'withdrawn'
    raw_text: Optional[str] = None
    parsed_json: Optional[dict] = None  # Optional: pre-parsed structure


class CreateApplicationRequest(BaseModel):
    apply_pack_id: Optional[UUID] = None
    job_target_id: Optional[UUID] = None
    status: str = "applied"
    notes: Optional[str] = None
    reminder_at: Optional[datetime] = None
    contact_email: Optional[str] = None
    contact_linkedin_url: Optional[str] = None
    contact_phone: Optional[str] = None


class UpdateApplicationRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    reminder_at: Optional[datetime] = None
    contact_email: Optional[str] = None
    contact_linkedin_url: Optional[str] = None
    contact_phone: Optional[str] = None


class JobScoutImportRequest(BaseModel):
    """Import job from JobScout directly (no URL parsing needed)."""
    job_id: Optional[str] = None  # JobScout job_id for auditing
    source: Optional[str] = Field(
        default="jobscout",
        description="Origin of import payload (e.g. jobscout|extension|manual)",
    )
    captured_from: Optional[str] = Field(
        default=None,
        description="Optional capture site identifier (e.g. linkedin|indeed|greenhouse|lever|ats)",
    )
    job_url: Optional[str] = None
    apply_url: Optional[str] = None
    title: str
    company: str
    location_raw: Optional[str] = None
    location: Optional[str] = None
    remote_type: Optional[str] = None
    employment_types: Optional[list[str]] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    description_text: Optional[str] = None
    # Optional JobScout-specific fields (stored in extracted_json)
    company_website: Optional[str] = None
    linkedin_url: Optional[str] = None
    ai_company_summary: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_requirements: Optional[str] = None
    ai_tech_stack: Optional[str] = None


# ==================== Trust Report Feedback (Community) ====================

class TrustFeedbackRequest(BaseModel):
    feedback_kind: str = Field(..., description="report|accuracy")
    dimension: str = Field("overall", description="overall|scam|ghost|staleness|link")
    value: Optional[str] = None
    comment: Optional[str] = None


# ==================== Helper: Require Authenticated User ====================

async def require_auth_user(
    auth_user: AuthUser = Depends(get_current_user),
) -> UUID:
    """
    Require authenticated Supabase user for Apply Workspace endpoints.
    
    Creates/updates the user record in the Apply DB with the Supabase UUID and email.
    This is the ONLY way to get a user_id for protected endpoints - no anonymous access.
    """
    async with db.connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, email, plan)
            VALUES ($1, $2, 'free')
            ON CONFLICT (user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
            """,
            auth_user.user_id,
            auth_user.email,
        )
    return auth_user.user_id


# ==================== Endpoints ====================

@router.post("/job/parse")
async def parse_job(
    request: JobIntakeRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """
    Parse a job URL or text into structured fields.
    Returns extracted job data and creates a job_target record.
    """
    if not request.job_url and not request.job_text:
        raise HTTPException(status_code=400, detail="Either job_url or job_text is required")
    
    async with db.connection() as conn:
        # Ensure user exists in this connection
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            # User doesn't exist, create it with the provided user_id
            await conn.execute(
                """
                INSERT INTO users (user_id, plan) 
                VALUES ($1, 'free')
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id
            )
        
        job_hash = apply_storage.hash_job_target(
            str(request.job_url) if request.job_url else None,
            request.job_text
        )
        
        # Check if already exists
        existing = await apply_storage.get_job_target_by_hash(conn, job_hash)
        if existing:
            existing_extracted = existing.get("extracted_json")
            if isinstance(existing_extracted, str):
                try:
                    existing_extracted = json.loads(existing_extracted)
                except Exception:
                    existing_extracted = {}
            elif existing_extracted is None:
                existing_extracted = {}
            if not isinstance(existing_extracted, dict):
                existing_extracted = {}

            return {
                "job_target_id": str(existing["job_target_id"]),
                "title": existing.get("title"),
                "company": existing.get("company"),
                "location": existing.get("location"),
                "remote_type": existing.get("remote_type"),
                "employment_type": existing.get("employment_type", []),
                "salary_min": existing.get("salary_min"),
                "salary_max": existing.get("salary_max"),
                "salary_currency": existing.get("salary_currency"),
                "description_text": existing.get("description_text"),
                "job_url": existing.get("job_url"),
                "apply_url": existing_extracted.get("apply_url") or existing.get("job_url"),  # Use job_url as fallback
                "extracted": True,
                "extraction_method": "cached",
            }
        
        # Parse the job
        if request.job_url:
            parse_result = await job_parser.parse_job_url(str(request.job_url))
            if not parse_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse job URL: {parse_result.get('error', 'Unknown error')}"
                )
            job_data = parse_result["data"]
            extraction_method = parse_result["extraction_method"]
        else:
            job_data = job_parser.parse_job_text(request.job_text)
            extraction_method = "text"

        # Ensure apply_url is persisted for Trust Report v2 (apply link health)
        extracted_json = job_data.get("extracted_json") or {}
        if isinstance(extracted_json, str):
            try:
                extracted_json = json.loads(extracted_json)
            except Exception:
                extracted_json = {}
        if not isinstance(extracted_json, dict):
            extracted_json = {}

        extracted_json.setdefault("source", "apply_parse")
        extracted_json["apply_url"] = job_data.get("apply_url") or job_data.get("job_url") or str(request.job_url)
        if job_data.get("company_website"):
            extracted_json.setdefault("company_website", job_data.get("company_website"))
        
        # Analyze job description to extract requirements, keywords, must-haves
        description_text = job_data.get("description_text") or request.job_text or ""
        job_analysis = await job_analyzer.analyze_job(description_text, use_ai=False)  # Use heuristic for now (faster)
        
        # Convert employment_type list to string if needed
        employment_type = job_data.get("employment_type")
        if isinstance(employment_type, list):
            employment_type = ", ".join(employment_type) if employment_type else None
        elif employment_type is None:
            employment_type = None
        
        # Create job target with extracted data
        job_target = await apply_storage.create_job_target(
            conn,
            user_id=user_id,
            job_url=str(request.job_url) if request.job_url else None,
            job_text=request.job_text,
            extracted_json=extracted_json,
            title=job_data.get("title"),
            company=job_data.get("company"),
            location=job_data.get("location"),
            remote_type=job_data.get("remote_type"),
            employment_type=employment_type,
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            salary_currency=job_data.get("salary_currency"),
            description_text=description_text,
            requirements=job_analysis.get("must_haves"),  # Store must-haves as requirements
            keywords=job_analysis.get("keywords"),
            must_haves=job_analysis.get("must_haves"),
            role_rubric=job_analysis.get("rubric"),
            html=job_data.get("html"),  # Store HTML for trust report regeneration
        )
        
        return {
            "job_target_id": str(job_target["job_target_id"]),
            "title": job_data.get("title"),
            "company": job_data.get("company"),
            "location": job_data.get("location"),
            "remote_type": job_data.get("remote_type"),
            "employment_type": job_data.get("employment_type", []),
            "salary_min": job_data.get("salary_min"),
            "salary_max": job_data.get("salary_max"),
            "salary_currency": job_data.get("salary_currency"),
            "description_text": job_data.get("description_text"),
            "job_url": job_data.get("job_url"),
            "apply_url": job_data.get("apply_url") or job_data.get("job_url"),
            "extracted": False,
            "extraction_method": extraction_method,
        }


@router.get("/job/target/{job_target_id}")
async def get_job_target(
    job_target_id: UUID,
    user_id: UUID = Depends(require_auth_user),
):
    """
    Get a job target by ID (for deep-linking from extension or Apply page).
    Returns a ParsedJob-like payload so the Apply page can load it without re-parsing.
    """
    async with db.connection() as conn:
        job_target = await apply_storage.get_job_target(conn, user_id=user_id, job_target_id=job_target_id)
    if not job_target:
        raise HTTPException(status_code=404, detail="Job target not found")
    extracted_json = job_target.get("extracted_json")
    if isinstance(extracted_json, str):
        try:
            extracted_json = json.loads(extracted_json)
        except Exception:
            extracted_json = {}
    elif extracted_json is None:
        extracted_json = {}
    apply_url = None
    if isinstance(extracted_json, dict):
        apply_url = extracted_json.get("apply_url")
    apply_url = apply_url or job_target.get("apply_url") or job_target.get("job_url")
    employment_type = job_target.get("employment_type")
    if isinstance(employment_type, str) and employment_type:
        employment_type = [s.strip() for s in employment_type.split(",") if s.strip()]
    elif not employment_type:
        employment_type = []
    return {
        "job_target_id": str(job_target["job_target_id"]),
        "title": job_target.get("title"),
        "company": job_target.get("company"),
        "location": job_target.get("location"),
        "remote_type": job_target.get("remote_type"),
        "employment_type": employment_type,
        "salary_min": job_target.get("salary_min"),
        "salary_max": job_target.get("salary_max"),
        "salary_currency": job_target.get("salary_currency"),
        "description_text": job_target.get("description_text"),
        "job_url": job_target.get("job_url"),
        "apply_url": apply_url,
        "extracted": True,
        "extraction_method": "job_target",
    }


@router.post("/job/import")
async def import_job_from_jobscout(
    request: JobScoutImportRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """
    Import a job from JobScout directly into Apply Workspace.
    Creates a job_target without re-scraping the URL.
    Stores JobScout-specific fields in extracted_json.
    """
    # Extension-originated saves should be strictly rate-limited (client-side + server-side).
    # This is a low-cost guardrail; multi-instance deployments should replace with shared limiter.
    if (request.source or "").lower() == "extension":
        check_rate_limit(user_id, job_capture_limiter)

    async with db.connection() as conn:
        # Ensure user exists
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            await conn.execute(
                """
                INSERT INTO users (user_id, plan) 
                VALUES ($1, 'free')
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id
            )
        
        # Build extracted_json with JobScout-specific fields
        extracted_json = {
            "source": (request.source or "jobscout").lower(),
            "job_id": request.job_id,
            "captured_from": (request.captured_from.lower() if request.captured_from else None),
            "apply_url": request.apply_url or request.job_url,
            "company_website": request.company_website,
            "linkedin_url": request.linkedin_url,
            "ai_company_summary": request.ai_company_summary,
            "ai_summary": request.ai_summary,
            "ai_requirements": request.ai_requirements,
            "ai_tech_stack": request.ai_tech_stack,
        }
        # Remove None values
        extracted_json = {k: v for k, v in extracted_json.items() if v is not None}
        
        # Use location_raw if provided, otherwise location
        location = request.location_raw or request.location
        
        # Convert employment_types list to string if needed
        employment_type = request.employment_types
        if isinstance(employment_type, list):
            employment_type = ", ".join(employment_type) if employment_type else None
        
        # Analyze job description to extract requirements, keywords, must-haves
        description_text = request.description_text or ""
        job_analysis = await job_analyzer.analyze_job(description_text, use_ai=False)  # Use heuristic for speed
        
        # Create job target directly (no URL parsing)
        job_target = await apply_storage.create_job_target(
            conn,
            user_id=user_id,
            job_url=request.job_url,
            job_text=description_text,  # Use description_text as job_text
            extracted_json=extracted_json,
            title=request.title,
            company=request.company,
            location=location,
            remote_type=request.remote_type,
            employment_type=employment_type,
            salary_min=request.salary_min,
            salary_max=request.salary_max,
            salary_currency=request.salary_currency,
            description_text=description_text,
            requirements=job_analysis.get("must_haves"),
            keywords=job_analysis.get("keywords"),
            must_haves=job_analysis.get("must_haves"),
            role_rubric=job_analysis.get("rubric"),
            html=None,  # No HTML since we're importing directly
        )

        return {
            "job_target_id": str(job_target["job_target_id"]),
            "title": request.title,
            "company": request.company,
            "location": location,
            "remote_type": request.remote_type,
            "employment_type": request.employment_types or [],
            "salary_min": request.salary_min,
            "salary_max": request.salary_max,
            "salary_currency": request.salary_currency,
            "description_text": description_text,
            "job_url": request.job_url,
            "apply_url": request.apply_url or request.job_url,
            "extracted": True,
            "extraction_method": "jobscout_import",
        }


if _HAS_MULTIPART:
    @router.post("/resume/upload")
    async def upload_resume(
        file: UploadFile = File(...),
        user_id: UUID = Depends(require_auth_user),
    ):
        """
        Upload a resume file (PDF or DOCX) and extract text.

        Returns extracted text that can be used for apply pack generation.
        """
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_lower = file.filename.lower()
        if not (file_lower.endswith(".pdf") or file_lower.endswith(".docx") or file_lower.endswith(".doc")):
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Supported: PDF, DOCX",
            )

        # Check file size (max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size: 10MB",
            )

        # Parse the file
        result = await resume_parser.parse_resume_file(file_content, file.filename)

        if result.get("error"):
            raise HTTPException(
                status_code=400,
                detail=result["error"],
            )

        if not result.get("text") or len(result["text"].strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Could not extract sufficient text from file. Please ensure the file is a valid resume.",
            )

        return {
            "resume_text": result["text"],
            "filename": file.filename,
            "size": len(file_content),
        }
else:
    @router.post("/resume/upload")
    async def upload_resume_unavailable(user_id: UUID = Depends(require_auth_user)):
        raise HTTPException(
            status_code=501,
            detail='Resume upload requires "python-multipart". Install backend dependencies: pip install -r backend/requirements.txt',
        )


@router.put("/job/{job_target_id}")
async def update_job_target(
    job_target_id: UUID,
    request: UpdateJobTargetRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """
    Update job target fields (for editable UI).
    """
    async with db.connection() as conn:
        # Verify ownership
        job_target = await conn.fetchrow(
            "SELECT user_id FROM job_targets WHERE job_target_id = $1",
            job_target_id
        )
        if not job_target:
            raise HTTPException(status_code=404, detail="Job target not found")
        if job_target["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Build update query dynamically
        updates = []
        values = []
        param_idx = 1
        
        if request.title is not None:
            updates.append(f"title = ${param_idx}")
            values.append(request.title)
            param_idx += 1
        if request.company is not None:
            updates.append(f"company = ${param_idx}")
            values.append(request.company)
            param_idx += 1
        if request.location is not None:
            updates.append(f"location = ${param_idx}")
            values.append(request.location)
            param_idx += 1
        if request.remote_type is not None:
            updates.append(f"remote_type = ${param_idx}")
            values.append(request.remote_type)
            param_idx += 1
        if request.employment_type is not None:
            updates.append(f"employment_type = ${param_idx}")
            values.append(request.employment_type)
            param_idx += 1
        if request.salary_min is not None:
            updates.append(f"salary_min = ${param_idx}")
            values.append(request.salary_min)
            param_idx += 1
        if request.salary_max is not None:
            updates.append(f"salary_max = ${param_idx}")
            values.append(request.salary_max)
            param_idx += 1
        if request.salary_currency is not None:
            updates.append(f"salary_currency = ${param_idx}")
            values.append(request.salary_currency)
            param_idx += 1
        if request.description_text is not None:
            updates.append(f"description_text = ${param_idx}")
            values.append(request.description_text)
            param_idx += 1
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append(f"updated_at = NOW()")
        values.append(job_target_id)
        
        query = f"""
            UPDATE job_targets 
            SET {', '.join(updates)}
            WHERE job_target_id = ${param_idx}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        return {
            "job_target_id": str(row["job_target_id"]),
            "title": row.get("title"),
            "company": row.get("company"),
            "location": row.get("location"),
            "remote_type": row.get("remote_type"),
            "employment_type": row.get("employment_type", []),
            "salary_min": row.get("salary_min"),
            "salary_max": row.get("salary_max"),
            "salary_currency": row.get("salary_currency"),
            "description_text": row.get("description_text"),
        }


@router.post("/job/{job_target_id}/trust")
async def generate_trust_report(
    job_target_id: UUID,
    force: bool = Query(False, description="Regenerate trust report even if cached"),
    refresh_apply_link: bool = Query(False, description="Re-test apply link even if cached"),
    user_id: UUID = Depends(require_auth_user),
):
    """
    Generate a trust report for a job target.
    Analyzes scam risk, ghost-likelihood, and staleness.
    """
    async with db.connection() as conn:
        # Get job target
        job_target = await conn.fetchrow(
            "SELECT * FROM job_targets WHERE job_target_id = $1",
            job_target_id
        )
        if not job_target:
            raise HTTPException(status_code=404, detail="Job target not found")
        
        # Check cache (unless forced)
        existing = await apply_storage.get_trust_report(conn, job_target_id)
        if existing and not force:
            # For cached reports, include cheap link warnings (no network)
            extracted_json = job_target.get("extracted_json")
            if isinstance(extracted_json, str):
                try:
                    extracted_json = json.loads(extracted_json)
                except Exception:
                    extracted_json = {}
            elif extracted_json is None:
                extracted_json = {}
            if not isinstance(extracted_json, dict):
                extracted_json = {}

            apply_url = (
                extracted_json.get("apply_url")
                or job_target.get("apply_url")
                or job_target.get("job_url")
            )
            link_warnings = _link_warnings_from_url(apply_url)

            community = await apply_storage.get_trust_report_feedback_summary(conn, job_target_id)
            penalty, community_reasons = _community_penalty(community)
            trust_score = existing.get("trust_score")
            trust_score_adj = max(0, int(trust_score) - penalty) if trust_score is not None else None
            payload = {
                "trust_report_id": str(existing["trust_report_id"]),
                "scam_risk": existing["scam_risk"],
                "scam_reasons": existing.get("scam_reasons", []) or [],
                "ghost_likelihood": existing["ghost_likelihood"],
                "ghost_reasons": existing.get("ghost_reasons", []) or [],
                "staleness_score": existing.get("staleness_score"),
                "staleness_reasons": existing.get("staleness_reasons"),
                "scam_score": existing.get("scam_score"),
                "ghost_score": existing.get("ghost_score"),
                "apply_link_status": existing.get("apply_link_status"),
                "apply_link_final_url": None,
                "apply_link_redirects": None,
                "apply_link_cached": True,
                "apply_link_warnings": link_warnings,
                "domain_consistency_reasons": existing.get("domain_consistency_reasons"),
                "trust_score": trust_score_adj,
            }
            return TrustReportResponse(
                **payload,
                verified_at=existing.get("created_at"),
                confidence=_build_confidence(payload),
                community=community,
                community_reasons=community_reasons,
                next_steps=_build_next_steps(payload),
            )
        
        # Parse dates
        posted_at = None
        expires_at = None
        if job_target.get("posted_at"):
            from datetime import datetime
            posted_at = job_target["posted_at"]
        if job_target.get("expires_at"):
            expires_at = job_target["expires_at"]
        
        # Get stored HTML if available
        stored_html = job_target.get("html")
        
        # Get extracted_json for additional context
        extracted_json = job_target.get("extracted_json")
        if isinstance(extracted_json, str):
            try:
                extracted_json = json.loads(extracted_json)
            except Exception:
                extracted_json = {}
        elif extracted_json is None:
            extracted_json = {}
        
        apply_url = extracted_json.get("apply_url") or job_target.get("apply_url")
        company_website = extracted_json.get("company_website")
        source = extracted_json.get("source")  # e.g., "jobscout", "remoteok"
        
        # Cached report for analyzer (optional)
        cached_report = dict(existing) if (existing and not refresh_apply_link) else None
        
        # Generate trust report
        report_data = await trust_analyzer.generate_trust_report(
            job_target_id=str(job_target_id),
            job_url=job_target.get("job_url"),
            description_text=job_target.get("description_text"),
            posted_at=posted_at,
            expires_at=expires_at,
            html=stored_html,  # Use stored HTML if available
            apply_url=apply_url,
            company_website=company_website,
            source=source,
            cached_trust_report=cached_report,
        )
        
        # Save trust report
        trust_report = await apply_storage.create_trust_report(
            conn,
            job_target_id=job_target_id,
            scam_risk=report_data["scam_risk"],
            scam_reasons=report_data["scam_reasons"],
            scam_score=report_data.get("scam_score"),
            ghost_likelihood=report_data["ghost_likelihood"],
            ghost_reasons=report_data["ghost_reasons"],
            ghost_score=report_data.get("ghost_score"),
            staleness_score=report_data["staleness_score"],
            staleness_reasons=report_data["staleness_reasons"],
            domain=report_data.get("domain"),
            extracted_emails=report_data.get("extracted_emails", []),
            extracted_phones=report_data.get("extracted_phones", []),
            apply_link_status=report_data.get("apply_link_status"),
            domain_consistency_reasons=report_data.get("domain_consistency_reasons", []),
            trust_score=report_data.get("trust_score"),
        )

        community = await apply_storage.get_trust_report_feedback_summary(conn, job_target_id)
        penalty, community_reasons = _community_penalty(community)
        raw_score = trust_report.get("trust_score") or report_data.get("trust_score")
        trust_score_adj = max(0, int(raw_score) - penalty) if raw_score is not None else None

        payload = {
            "trust_report_id": str(trust_report["trust_report_id"]),
            "scam_risk": trust_report["scam_risk"],
            "scam_reasons": trust_report.get("scam_reasons", []) or [],
            "ghost_likelihood": trust_report["ghost_likelihood"],
            "ghost_reasons": trust_report.get("ghost_reasons", []) or [],
            "staleness_score": trust_report.get("staleness_score"),
            "staleness_reasons": trust_report.get("staleness_reasons"),
            "scam_score": trust_report.get("scam_score") or report_data.get("scam_score"),
            "ghost_score": trust_report.get("ghost_score") or report_data.get("ghost_score"),
            "apply_link_status": trust_report.get("apply_link_status") or report_data.get("apply_link_status"),
            "apply_link_final_url": report_data.get("apply_link_final_url"),
            "apply_link_redirects": report_data.get("apply_link_redirects"),
            "apply_link_cached": report_data.get("apply_link_cached", False),
            "apply_link_warnings": report_data.get("apply_link_warnings") or _link_warnings_from_url(apply_url),
            "domain_consistency_reasons": trust_report.get("domain_consistency_reasons") or report_data.get("domain_consistency_reasons"),
            "trust_score": trust_score_adj,
        }

        return TrustReportResponse(
            **payload,
            verified_at=trust_report.get("created_at"),
            confidence=_build_confidence(payload),
            community=community,
            community_reasons=community_reasons,
            next_steps=_build_next_steps(payload),
        )


@router.post("/job/{job_target_id}/trust/feedback")
async def submit_trust_feedback(
    job_target_id: UUID,
    request: TrustFeedbackRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """Community feedback loop for Trust Reports."""
    feedback_kind = (request.feedback_kind or "").strip().lower()
    dimension = (request.dimension or "overall").strip().lower()
    value = (request.value or None)
    if isinstance(value, str):
        value = value.strip().lower() or None
    comment = (request.comment or None)
    if isinstance(comment, str):
        comment = comment.strip()
        if not comment:
            comment = None
        if comment and len(comment) > 800:
            comment = comment[:800]

    if feedback_kind not in ("report", "accuracy"):
        raise HTTPException(status_code=400, detail="feedback_kind must be 'report' or 'accuracy'")
    if dimension not in ("overall", "scam", "ghost", "staleness", "link"):
        raise HTTPException(status_code=400, detail="dimension must be overall|scam|ghost|staleness|link")

    if feedback_kind == "accuracy":
        if value not in ("accurate", "inaccurate"):
            raise HTTPException(status_code=400, detail="value must be 'accurate' or 'inaccurate' for accuracy feedback")
    else:
        # 'report' feedback: accept a small allowlist to keep aggregation stable
        if value is None:
            value = "other"
        if value not in ("scam", "ghost", "expired", "other"):
            value = "other"

    async with db.connection() as conn:
        # Ensure job target exists
        jt = await conn.fetchval("SELECT 1 FROM job_targets WHERE job_target_id = $1", job_target_id)
        if not jt:
            raise HTTPException(status_code=404, detail="Job target not found")

        await apply_storage.create_trust_report_feedback(
            conn,
            job_target_id=job_target_id,
            user_id=user_id,
            feedback_kind=feedback_kind,
            dimension=dimension,
            value=value,
            comment=comment,
        )
        summary = await apply_storage.get_trust_report_feedback_summary(conn, job_target_id)
        return {"ok": True, "community": summary}


@router.post("/pack/generate")
async def generate_apply_pack(
    request: GeneratePackRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """
    Generate an apply pack (tailored resume content, cover note, ATS checklist).
    Checks rate limit and quota before generating.
    """
    # Rate limit check (10 requests per minute per user)
    check_rate_limit(user_id, apply_pack_limiter)
    
    async with db.connection() as conn:
        # Check quota
        quota = await apply_storage.check_user_quota(conn, user_id, "apply_pack")
        if not quota["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Quota exceeded. {quota.get('used', 0)}/{quota.get('limit', 0)} apply packs used this month."
            )
        
        # Get or create resume
        resume_hash = apply_storage.hash_resume(request.resume_text)
        resume = await apply_storage.get_resume_by_hash(conn, user_id, resume_hash)
        if not resume:
            # Analyze resume first
            resume_analysis = await resume_analyzer.analyze_resume(request.resume_text, use_ai=request.use_ai)
            
            resume = await apply_storage.create_resume_version(
                conn,
                user_id=user_id,
                resume_text=request.resume_text,
                extracted_skills=resume_analysis.get("skills"),
                extracted_seniority=resume_analysis.get("seniority"),
                extracted_bullets=resume_analysis.get("bullets"),
            )
        else:
            # Use existing analysis
            import json
            skills = resume.get("extracted_skills")
            bullets = resume.get("extracted_bullets")
            
            if isinstance(skills, str):
                try:
                    skills = json.loads(skills)
                except Exception:
                    skills = []
            elif skills is None:
                skills = []
            
            if isinstance(bullets, str):
                try:
                    bullets = json.loads(bullets)
                except Exception:
                    bullets = []
            elif bullets is None:
                bullets = []
            
            resume_analysis = {
                "skills": skills,
                "seniority": resume.get("extracted_seniority") or "mid",
                "bullets": bullets,
            }
        
        # Get or create job target
        job_hash = apply_storage.hash_job_target(
            str(request.job_url) if request.job_url else None,
            request.job_text
        )
        job_target = await apply_storage.get_job_target_by_hash(conn, job_hash)
        if not job_target:
            # Parse job if needed
            if request.job_url:
                parse_result = await job_parser.parse_job_url(str(request.job_url))
                if parse_result["success"]:
                    job_data = parse_result["data"]
                else:
                    raise HTTPException(status_code=400, detail="Failed to parse job URL")
            else:
                job_data = job_parser.parse_job_text(request.job_text)
            
            # Analyze job
            job_analysis = await job_analyzer.analyze_job(
                job_data.get("description_text", request.job_text),
                use_ai=request.use_ai
            )
            
            job_target = await apply_storage.create_job_target(
                conn,
                user_id=user_id,
                job_url=str(request.job_url) if request.job_url else None,
                job_text=request.job_text,
                title=job_data.get("title"),
                company=job_data.get("company"),
                location=job_data.get("location"),
                description_text=job_data.get("description_text"),
                must_haves=job_analysis.get("must_haves"),
                keywords=job_analysis.get("keywords"),
                role_rubric=job_analysis.get("rubric"),
            )
        else:
            # Use existing job analysis
            import json
            must_haves = job_target.get("must_haves")
            keywords = job_target.get("keywords")
            
            if isinstance(must_haves, str):
                try:
                    must_haves = json.loads(must_haves)
                except Exception:
                    must_haves = []
            elif must_haves is None:
                must_haves = []
            
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except Exception:
                    keywords = []
            elif keywords is None:
                keywords = []
            
            job_analysis = {
                "must_haves": must_haves,
                "keywords": keywords,
                "rubric": job_target.get("role_rubric") or "",
            }
        
        # Check if apply pack already exists (cached)
        pack_hash = apply_storage.hash_apply_pack(resume_hash, job_hash)
        existing_pack = await apply_storage.get_apply_pack_by_hash(conn, user_id, pack_hash)
        
        if existing_pack and not request.use_ai:
            # Return cached version
            import json
            bullets = existing_pack.get("tailored_bullets")
            if isinstance(bullets, str):
                try:
                    bullets = json.loads(bullets)
                except Exception:
                    bullets = []
            elif bullets is None:
                bullets = []
            
            checklist = existing_pack.get("ats_checklist")
            if isinstance(checklist, str):
                try:
                    checklist = json.loads(checklist)
                except Exception:
                    checklist = {}
            elif checklist is None:
                checklist = {}
            
            return ApplyPackResponse(
                apply_pack_id=str(existing_pack["apply_pack_id"]),
                tailored_summary=existing_pack.get("tailored_summary"),
                tailored_bullets=bullets,
                cover_note=existing_pack.get("cover_note"),
                ats_checklist=checklist,
                keyword_coverage=existing_pack.get("keyword_coverage"),
            )
        
        # Extract company info from job_target (including from extracted_json for JobScout imports)
        import json
        extracted_json = job_target.get("extracted_json")
        if isinstance(extracted_json, str):
            try:
                extracted_json = json.loads(extracted_json)
            except Exception:
                extracted_json = {}
        elif extracted_json is None:
            extracted_json = {}
        
        job_title = job_target.get("title")
        company_name = job_target.get("company")
        company_summary = extracted_json.get("ai_company_summary") or extracted_json.get("company_summary")
        company_website = extracted_json.get("company_website")
        
        # Get learning context from past feedback
        learning_context = None
        if request.use_ai:
            try:
                learning_context = await learning_summary.build_learning_summary(user_id, limit=50)
            except Exception as e:
                # Don't fail if learning summary fails
                print(f"Warning: Failed to build learning summary: {e}")
        
        # Generate apply pack
        pack_data = await apply_pack_generator.generate_apply_pack(
            resume_text=request.resume_text,
            resume_analysis=resume_analysis,
            job_description=job_target.get("description_text", request.job_text or ""),
            job_analysis=job_analysis,
            use_ai=request.use_ai,
            job_title=job_title,
            company_name=company_name,
            company_summary=company_summary,
            company_website=company_website,
            learning_context=learning_context,
        )
        
        # Convert UUIDs if needed (asyncpg returns UUID objects, not strings)
        resume_id_val = resume["resume_id"]
        if not isinstance(resume_id_val, UUID):
            resume_id_val = UUID(resume_id_val) if isinstance(resume_id_val, str) else UUID(str(resume_id_val))
        
        job_target_id_val = job_target["job_target_id"]
        if not isinstance(job_target_id_val, UUID):
            job_target_id_val = UUID(job_target_id_val) if isinstance(job_target_id_val, str) else UUID(str(job_target_id_val))
        
        # Save apply pack
        apply_pack = await apply_storage.create_apply_pack(
            conn,
            user_id=user_id,
            resume_id=resume_id_val,
            job_target_id=job_target_id_val,
            pack_hash=pack_hash,
            tailored_summary=pack_data.get("tailored_summary"),
            tailored_bullets=pack_data.get("tailored_bullets"),
            cover_note=pack_data.get("cover_note"),
            ats_checklist=pack_data.get("ats_checklist"),
            keyword_coverage=pack_data.get("keyword_coverage"),
        )
        
        # Record usage
        apply_pack_id_val = apply_pack["apply_pack_id"]
        if not isinstance(apply_pack_id_val, UUID):
            apply_pack_id_val = UUID(apply_pack_id_val) if isinstance(apply_pack_id_val, str) else UUID(str(apply_pack_id_val))
        await apply_storage.record_usage(conn, user_id, "apply_pack", apply_pack_id_val)
        
        import json
        bullets = pack_data.get("tailored_bullets", [])
        checklist = pack_data.get("ats_checklist", {})
        
        return ApplyPackResponse(
            apply_pack_id=str(apply_pack["apply_pack_id"]),
            tailored_summary=pack_data.get("tailored_summary"),
            tailored_bullets=bullets,
            cover_note=pack_data.get("cover_note"),
            ats_checklist=checklist,
            keyword_coverage=pack_data.get("keyword_coverage"),
        )


@router.get("/pack/{apply_pack_id}")
async def get_apply_pack(
    apply_pack_id: UUID,
    user_id: UUID = Depends(require_auth_user),
):
    """Get an apply pack by ID."""
    async with db.connection() as conn:
        # Fetch apply pack with related data
        row = await conn.fetchrow(
            """
            SELECT ap.*, rv.resume_text, jt.title, jt.company, jt.job_url, jt.description_text as job_description
            FROM apply_packs ap
            LEFT JOIN resume_versions rv ON ap.resume_id = rv.resume_id
            LEFT JOIN job_targets jt ON ap.job_target_id = jt.job_target_id
            WHERE ap.apply_pack_id = $1 AND ap.user_id = $2
            """,
            apply_pack_id, user_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Apply pack not found")
        
        # Parse JSON fields
        import json
        tailored_bullets = row.get("tailored_bullets")
        if isinstance(tailored_bullets, str):
            try:
                tailored_bullets = json.loads(tailored_bullets)
            except Exception:
                tailored_bullets = []
        elif tailored_bullets is None:
            tailored_bullets = []
        
        ats_checklist = row.get("ats_checklist")
        if isinstance(ats_checklist, str):
            try:
                ats_checklist = json.loads(ats_checklist)
            except Exception:
                ats_checklist = {}
        elif ats_checklist is None:
            ats_checklist = {}
        
        return ApplyPackResponse(
            apply_pack_id=str(row["apply_pack_id"]),
            tailored_summary=row.get("tailored_summary"),
            tailored_bullets=tailored_bullets,
            cover_note=row.get("cover_note"),
            ats_checklist=ats_checklist,
            keyword_coverage=float(row.get("keyword_coverage", 0)) if row.get("keyword_coverage") else None,
        )


@router.get("/history")
async def get_history(
    user_id: UUID = Depends(require_auth_user),
    limit: int = 50,
    offset: int = 0,
):
    """Get user's apply pack history."""
    async with db.connection() as conn:
        packs = await apply_storage.get_user_apply_packs(conn, user_id, limit, offset)
        return {
            "packs": packs,
            "total": len(packs),
        }


@router.get("/pack/{apply_pack_id}/export")
async def export_apply_pack_docx(
    apply_pack_id: UUID,
    format: str = "combined",  # "resume", "cover", or "combined"
    user_id: UUID = Depends(require_auth_user),
):
    """
    Export apply pack as downloadable file.
    
    Formats:
    - "resume": Single DOCX with tailored resume
    - "cover": Single DOCX with personalized cover letter
    - "combined": ZIP file containing both resume.docx and cover_letter.docx
    
    Paid feature only.
    """
    async with db.connection() as conn:
        # Check quota (paid only)
        quota = await apply_storage.check_user_quota(conn, user_id, "docx_export")
        if not quota["allowed"]:
            raise HTTPException(
                status_code=403,
                detail="DOCX export is only available for paid plans. Upgrade to export your apply packs."
            )
        
        # Get apply pack
        apply_pack = await conn.fetchrow(
            """
            SELECT ap.*, rv.resume_text, jt.title, jt.company
            FROM apply_packs ap
            LEFT JOIN resume_versions rv ON ap.resume_id = rv.resume_id
            LEFT JOIN job_targets jt ON ap.job_target_id = jt.job_target_id
            WHERE ap.apply_pack_id = $1 AND ap.user_id = $2
            """,
            apply_pack_id, user_id
        )
        
        if not apply_pack:
            raise HTTPException(status_code=404, detail="Apply pack not found")
        
        # Parse JSON fields
        import json
        tailored_bullets = apply_pack.get("tailored_bullets")
        if isinstance(tailored_bullets, str):
            try:
                tailored_bullets = json.loads(tailored_bullets)
            except Exception:
                tailored_bullets = []
        elif tailored_bullets is None:
            tailored_bullets = []
        
        # Generate files
        try:
            from backend.app.services import docx_generator
            
            # Parse resume to extract applicant info for cover letter
            resume_text = apply_pack.get("resume_text", "")
            parsed_resume = docx_generator._parse_resume_into_structure(resume_text) if resume_text else {}
            
            # Extract applicant contact info
            applicant_name = parsed_resume.get('name', '')
            applicant_location = parsed_resume.get('location', '')
            applicant_email = None
            applicant_phone = None
            applicant_linkedin = None
            
            for contact in parsed_resume.get('contact', []):
                if contact.get('type') == 'email' and not applicant_email:
                    applicant_email = contact.get('value')
                elif contact.get('type') == 'phone' and not applicant_phone:
                    applicant_phone = contact.get('value')
                elif contact.get('type') == 'linkedin' and not applicant_linkedin:
                    applicant_linkedin = contact.get('url', contact.get('value'))
            
            if format == "resume":
                buffer = docx_generator.generate_resume_docx(
                    tailored_summary=apply_pack.get("tailored_summary", ""),
                    tailored_bullets=tailored_bullets,
                    original_resume_text=resume_text,
                )
                filename = "tailored_resume.docx"
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                
            elif format == "cover":
                buffer = docx_generator.generate_cover_note_docx(
                    cover_note=apply_pack.get("cover_note", ""),
                    job_title=apply_pack.get("title"),
                    company_name=apply_pack.get("company"),
                    applicant_name=applicant_name,
                    applicant_email=applicant_email,
                    applicant_phone=applicant_phone,
                    applicant_location=applicant_location,
                    applicant_linkedin=applicant_linkedin,
                )
                filename = "cover_letter.docx"
                media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                
            else:  # combined - returns ZIP file
                buffer = docx_generator.generate_apply_pack_zip(
                    tailored_summary=apply_pack.get("tailored_summary", ""),
                    tailored_bullets=tailored_bullets,
                    cover_note=apply_pack.get("cover_note", ""),
                    job_title=apply_pack.get("title"),
                    company_name=apply_pack.get("company"),
                    original_resume_text=resume_text,
                )
                filename = "apply_pack.zip"
                media_type = "application/zip"

            # Record usage
            await apply_storage.record_usage(conn, user_id, "docx_export", apply_pack_id)
            
            return StreamingResponse(
                buffer,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
            
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="DOCX export not available. python-docx package not installed."
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate export: {str(e)}")


@router.post("/application")
async def create_application(
    request: CreateApplicationRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """Create a tracked application. Checks tracking quota for free users."""
    async with db.connection() as conn:
        # Check tracking quota (free users have limited active applications)
        quota = await apply_storage.check_user_quota(conn, user_id, "tracking")
        if not quota["allowed"]:
            raise HTTPException(
                status_code=403,
                detail=f"Tracking limit reached. {quota.get('used', 0)}/{quota.get('limit', 0)} active applications. Upgrade to track unlimited applications."
            )
        
        # Verify ownership if IDs provided
        if request.apply_pack_id:
            pack = await conn.fetchrow(
                "SELECT user_id FROM apply_packs WHERE apply_pack_id = $1",
                request.apply_pack_id
            )
            if not pack or pack["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Apply pack not found")
        
        if request.job_target_id:
            job = await conn.fetchrow(
                "SELECT user_id FROM job_targets WHERE job_target_id = $1",
                request.job_target_id
            )
            if job and job["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Job target not found")
        
        application = await apply_storage.create_application(
            conn,
            user_id=user_id,
            apply_pack_id=request.apply_pack_id,
            job_target_id=request.job_target_id,
            status=request.status,
            notes=request.notes,
            reminder_at=request.reminder_at,
            contact_email=request.contact_email,
            contact_linkedin_url=request.contact_linkedin_url,
            contact_phone=request.contact_phone,
        )
        
        return {
            "application_id": str(application["application_id"]),
            "apply_pack_id": str(application["apply_pack_id"]) if application.get("apply_pack_id") else None,
            "job_target_id": str(application["job_target_id"]) if application.get("job_target_id") else None,
            "status": application["status"],
            "applied_at": application["applied_at"].isoformat() if application.get("applied_at") else None,
            "interview_at": application["interview_at"].isoformat() if application.get("interview_at") else None,
            "offer_at": application["offer_at"].isoformat() if application.get("offer_at") else None,
            "rejected_at": application["rejected_at"].isoformat() if application.get("rejected_at") else None,
            "notes": application.get("notes"),
            "reminder_at": application["reminder_at"].isoformat() if application.get("reminder_at") else None,
            "contact_email": application.get("contact_email"),
            "contact_linkedin_url": application.get("contact_linkedin_url"),
            "contact_phone": application.get("contact_phone"),
        }


@router.get("/insights")
async def get_insights(
    user_id: UUID = Depends(require_auth_user),
):
    """Aggregated feedback insights for recommendation cards (outcomes, rejection reasons)."""
    async with db.connection() as conn:
        insights = await apply_storage.get_user_feedback_insights(conn, user_id=user_id)
    return insights


@router.get("/application")
async def get_applications(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(require_auth_user),
):
    """Get user's tracked applications."""
    async with db.connection() as conn:
        applications = await apply_storage.get_user_applications(
            conn,
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        
        return {
            "applications": [
                {
                    "application_id": str(app["application_id"]),
                    "apply_pack_id": str(app["apply_pack_id"]) if app.get("apply_pack_id") else None,
                    "job_target_id": str(app["job_target_id"]) if app.get("job_target_id") else None,
                    "status": app["status"],
                    "title": app.get("title"),
                    "company": app.get("company"),
                    "job_url": app.get("job_url"),
                    "applied_at": app["applied_at"].isoformat() if app.get("applied_at") else None,
                    "interview_at": app["interview_at"].isoformat() if app.get("interview_at") else None,
                    "offer_at": app["offer_at"].isoformat() if app.get("offer_at") else None,
                    "rejected_at": app["rejected_at"].isoformat() if app.get("rejected_at") else None,
                    "notes": app.get("notes"),
                    "reminder_at": app["reminder_at"].isoformat() if app.get("reminder_at") else None,
                    "contact_email": app.get("contact_email"),
                    "contact_linkedin_url": app.get("contact_linkedin_url"),
                    "contact_phone": app.get("contact_phone"),
                }
                for app in applications
            ],
            "total": len(applications),
        }


@router.put("/application/{application_id}")
async def update_application(
    application_id: UUID,
    request: UpdateApplicationRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """Update a tracked application."""
    async with db.connection() as conn:
        # Verify ownership
        app = await conn.fetchrow(
            "SELECT user_id FROM applications WHERE application_id = $1",
            application_id
        )
        if not app or app["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Build update query
        updates = []
        values = []
        param_idx = 1
        
        # If status is changing, automatically set timeline timestamps (unless explicitly provided later)
        new_status = request.status
        now = datetime.utcnow()

        if request.status is not None:
            updates.append(f"status = ${param_idx}")
            values.append(request.status)
            param_idx += 1
        if request.notes is not None:
            updates.append(f"notes = ${param_idx}")
            values.append(request.notes)
            param_idx += 1
        if request.reminder_at is not None:
            updates.append(f"reminder_at = ${param_idx}")
            values.append(request.reminder_at)
            param_idx += 1
        if request.contact_email is not None:
            updates.append(f"contact_email = ${param_idx}")
            values.append(request.contact_email)
            param_idx += 1
        if request.contact_linkedin_url is not None:
            updates.append(f"contact_linkedin_url = ${param_idx}")
            values.append(request.contact_linkedin_url)
            param_idx += 1
        if request.contact_phone is not None:
            updates.append(f"contact_phone = ${param_idx}")
            values.append(request.contact_phone)
            param_idx += 1

        if new_status == "interview":
            updates.append(f"interview_at = COALESCE(interview_at, ${param_idx})")
            values.append(now)
            param_idx += 1
        elif new_status == "offer":
            updates.append(f"offer_at = COALESCE(offer_at, ${param_idx})")
            values.append(now)
            param_idx += 1
        elif new_status == "rejected":
            updates.append(f"rejected_at = COALESCE(rejected_at, ${param_idx})")
            values.append(now)
            param_idx += 1
        elif new_status == "applied":
            updates.append(f"applied_at = COALESCE(applied_at, ${param_idx})")
            values.append(now)
            param_idx += 1
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = NOW()")
        values.append(application_id)
        
        query = f"""
            UPDATE applications 
            SET {', '.join(updates)}
            WHERE application_id = ${param_idx}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        return {
            "application_id": str(row["application_id"]),
            "status": row["status"],
            "notes": row.get("notes"),
            "reminder_at": row["reminder_at"].isoformat() if row.get("reminder_at") else None,
            "contact_email": row.get("contact_email"),
            "contact_linkedin_url": row.get("contact_linkedin_url"),
            "contact_phone": row.get("contact_phone"),
        }


@router.get("/quota")
async def get_quota(
    user_id: UUID = Depends(require_auth_user),
):
    """Get user's current quota status including apply packs, exports, and tracking."""
    async with db.connection() as conn:
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        apply_pack_quota = await apply_storage.check_user_quota(conn, user_id, "apply_pack")
        docx_quota = await apply_storage.check_user_quota(conn, user_id, "docx_export")
        tracking_quota = await apply_storage.check_user_quota(conn, user_id, "tracking")
        
        return {
            "plan": user.get("plan", "free"),
            "subscription_status": user.get("subscription_status"),
            "apply_packs": apply_pack_quota,
            "docx_export": docx_quota,
            "tracking": tracking_quota,
        }


@router.post("/application/{application_id}/feedback")
async def create_application_feedback(
    application_id: UUID,
    request: ApplicationFeedbackRequest,
    user_id: UUID = Depends(require_auth_user),
):
    """Store feedback for an application (rejection, shortlist, offer, etc.)."""
    async with db.connection() as conn:
        # Verify ownership
        app = await conn.fetchrow(
            "SELECT user_id FROM applications WHERE application_id = $1",
            application_id
        )
        if not app or app["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Parse feedback heuristically if not provided
        parsed_json = request.parsed_json
        if not parsed_json and request.raw_text:
            parsed_json = _parse_feedback_heuristic(request.raw_text, request.feedback_type)
        
        # Store feedback
        feedback = await apply_storage.create_application_feedback(
            conn,
            application_id=application_id,
            feedback_type=request.feedback_type,
            raw_text=request.raw_text,
            parsed_json=parsed_json,
        )
        
        # Parse JSON if stored as string
        parsed_data = feedback.get("parsed_json")
        if isinstance(parsed_data, str):
            try:
                parsed_data = json.loads(parsed_data)
            except Exception:
                parsed_data = {}
        elif parsed_data is None:
            parsed_data = {}
        
        return {
            "feedback_id": str(feedback["feedback_id"]),
            "feedback_type": feedback["feedback_type"],
            "raw_text": feedback.get("raw_text"),
            "parsed_json": parsed_data,
            "created_at": feedback["created_at"].isoformat() if feedback.get("created_at") else None,
        }


@router.get("/application/{application_id}/feedback")
async def get_application_feedback(
    application_id: UUID,
    user_id: UUID = Depends(require_auth_user),
):
    """Get all feedback for an application."""
    async with db.connection() as conn:
        # Verify ownership
        app = await conn.fetchrow(
            "SELECT user_id FROM applications WHERE application_id = $1",
            application_id
        )
        if not app or app["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Application not found")
        
        feedback_list = await apply_storage.get_application_feedback(conn, application_id)
        
        # Parse JSON fields
        result = []
        for fb in feedback_list:
            parsed_data = fb.get("parsed_json")
            if isinstance(parsed_data, str):
                try:
                    parsed_data = json.loads(parsed_data)
                except Exception:
                    parsed_data = {}
            elif parsed_data is None:
                parsed_data = {}
            
            result.append({
                "feedback_id": str(fb["feedback_id"]),
                "feedback_type": fb["feedback_type"],
                "raw_text": fb.get("raw_text"),
                "parsed_json": parsed_data,
                "created_at": fb["created_at"].isoformat() if fb.get("created_at") else None,
            })
        
        return {"feedback": result}


def _parse_feedback_heuristic(raw_text: str, feedback_type: str) -> dict:
    """Heuristically parse feedback text into structured data."""
    text_lower = raw_text.lower()
    
    # Reason categories
    reason_categories = []
    signals = []
    
    # Common rejection reasons
    if "senior" in text_lower or "seniority" in text_lower:
        reason_categories.append("seniority")
    if "skill" in text_lower and ("gap" in text_lower or "missing" in text_lower):
        reason_categories.append("skills_gap")
    if "sponsor" in text_lower or "visa" in text_lower:
        reason_categories.append("sponsorship")
    if "location" in text_lower or "remote" in text_lower:
        reason_categories.append("location")
    if "compensation" in text_lower or "salary" in text_lower or "budget" in text_lower:
        reason_categories.append("comp")
    if "experience" in text_lower and ("years" in text_lower or "level" in text_lower):
        reason_categories.append("experience_level")
    
    # Extract keywords/signals
    keywords = ["python", "javascript", "react", "node", "aws", "docker", "kubernetes",
                "leadership", "management", "team", "agile", "scrum"]
    for keyword in keywords:
        if keyword in text_lower:
            signals.append(keyword)
    
    decision = feedback_type  # Use feedback_type as decision
    
    return {
        "decision": decision,
        "reason_categories": reason_categories,
        "signals": signals[:10],  # Limit to 10
    }
