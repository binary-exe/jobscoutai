"""
API endpoints for Apply Workspace V1.

Handles job parsing, trust reports, resume processing, and apply pack generation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Header, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl

from backend.app.core.database import db
from backend.app.storage import apply_storage
from backend.app.services import job_parser
from backend.app.services import trust_analyzer
from backend.app.services import resume_analyzer
from backend.app.services import resume_parser
from backend.app.services import job_analyzer
from backend.app.services import apply_pack_generator

router = APIRouter(prefix="/apply", tags=["apply"])


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


# ==================== Helper: Get or Create User ====================

async def get_user_id(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> UUID:
    """Get or create user from header. For now, we use anonymous users."""
    if x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError:
            pass
    
    # Create anonymous user
    async with db.connection() as conn:
        user = await apply_storage.get_or_create_user(conn)
        return UUID(user["user_id"])


# ==================== Endpoints ====================

@router.post("/job/parse")
async def parse_job(
    request: JobIntakeRequest,
    user_id: UUID = Depends(get_user_id),
):
    """
    Parse a job URL or text into structured fields.
    Returns extracted job data and creates a job_target record.
    """
    if not request.job_url and not request.job_text:
        raise HTTPException(status_code=400, detail="Either job_url or job_text is required")
    
    async with db.connection() as conn:
        job_hash = apply_storage.hash_job_target(
            str(request.job_url) if request.job_url else None,
            request.job_text
        )
        
        # Check if already exists
        existing = await apply_storage.get_job_target_by_hash(conn, job_hash)
        if existing:
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
                "apply_url": existing.get("job_url"),  # Use job_url as fallback
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
        
        # Analyze job description to extract requirements, keywords, must-haves
        description_text = job_data.get("description_text") or request.job_text or ""
        job_analysis = await job_analyzer.analyze_job(description_text, use_ai=False)  # Use heuristic for now (faster)
        
        # Create job target with extracted data
        job_target = await apply_storage.create_job_target(
            conn,
            user_id=user_id,
            job_url=str(request.job_url) if request.job_url else None,
            job_text=request.job_text,
            extracted_json=job_data.get("extracted_json"),
            title=job_data.get("title"),
            company=job_data.get("company"),
            location=job_data.get("location"),
            remote_type=job_data.get("remote_type"),
            employment_type=job_data.get("employment_type"),
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


@router.post("/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_user_id),
):
    """
    Upload a resume file (PDF or DOCX) and extract text.
    
    Returns extracted text that can be used for apply pack generation.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_lower = file.filename.lower()
    if not (file_lower.endswith('.pdf') or file_lower.endswith('.docx') or file_lower.endswith('.doc')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported: PDF, DOCX"
        )
    
    # Check file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: 10MB"
        )
    
    # Parse the file
    result = await resume_parser.parse_resume_file(file_content, file.filename)
    
    if result.get("error"):
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )
    
    if not result.get("text") or len(result["text"].strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from file. Please ensure the file is a valid resume."
        )
    
    return {
        "resume_text": result["text"],
        "filename": file.filename,
        "size": len(file_content),
    }


@router.put("/job/{job_target_id}")
async def update_job_target(
    job_target_id: UUID,
    request: UpdateJobTargetRequest,
    user_id: UUID = Depends(get_user_id),
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
    user_id: UUID = Depends(get_user_id),
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
        
        # Check if trust report already exists
        existing = await apply_storage.get_trust_report(conn, job_target_id)
        if existing:
            return TrustReportResponse(
                trust_report_id=str(existing["trust_report_id"]),
                scam_risk=existing["scam_risk"],
                scam_reasons=existing.get("scam_reasons", []),
                ghost_likelihood=existing["ghost_likelihood"],
                ghost_reasons=existing.get("ghost_reasons", []),
                staleness_score=existing.get("staleness_score"),
                staleness_reasons=existing.get("staleness_reasons"),
                scam_score=None,  # Not stored in DB yet
                ghost_score=None,  # Not stored in DB yet
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
        
        # Generate trust report
        report_data = await trust_analyzer.generate_trust_report(
            job_target_id=str(job_target_id),
            job_url=job_target.get("job_url"),
            description_text=job_target.get("description_text"),
            posted_at=posted_at,
            expires_at=expires_at,
            html=stored_html,  # Use stored HTML if available
        )
        
        # Save trust report
        trust_report = await apply_storage.create_trust_report(
            conn,
            job_target_id=job_target_id,
            scam_risk=report_data["scam_risk"],
            scam_reasons=report_data["scam_reasons"],
            ghost_likelihood=report_data["ghost_likelihood"],
            ghost_reasons=report_data["ghost_reasons"],
            staleness_score=report_data["staleness_score"],
            staleness_reasons=report_data["staleness_reasons"],
            domain=report_data.get("domain"),
            extracted_emails=report_data.get("extracted_emails", []),
            extracted_phones=report_data.get("extracted_phones", []),
            apply_link_status=report_data.get("apply_link_status"),
        )
        
        return TrustReportResponse(
            trust_report_id=str(trust_report["trust_report_id"]),
            scam_risk=trust_report["scam_risk"],
            scam_reasons=trust_report.get("scam_reasons", []),
            ghost_likelihood=trust_report["ghost_likelihood"],
            ghost_reasons=trust_report.get("ghost_reasons", []),
            staleness_score=trust_report.get("staleness_score"),
            staleness_reasons=trust_report.get("staleness_reasons"),
            scam_score=report_data.get("scam_score"),
            ghost_score=report_data.get("ghost_score"),
        )


@router.post("/pack/generate")
async def generate_apply_pack(
    request: GeneratePackRequest,
    user_id: UUID = Depends(get_user_id),
):
    """
    Generate an apply pack (tailored resume content, cover note, ATS checklist).
    Checks quota before generating.
    """
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
        resume = await apply_storage.get_resume_by_hash(conn, resume_hash)
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
                except:
                    skills = []
            elif skills is None:
                skills = []
            
            if isinstance(bullets, str):
                try:
                    bullets = json.loads(bullets)
                except:
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
                except:
                    must_haves = []
            elif must_haves is None:
                must_haves = []
            
            if isinstance(keywords, str):
                try:
                    keywords = json.loads(keywords)
                except:
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
        existing_pack = await apply_storage.get_apply_pack_by_hash(conn, pack_hash)
        
        if existing_pack and not request.use_ai:
            # Return cached version
            import json
            bullets = existing_pack.get("tailored_bullets")
            if isinstance(bullets, str):
                try:
                    bullets = json.loads(bullets)
                except:
                    bullets = []
            elif bullets is None:
                bullets = []
            
            checklist = existing_pack.get("ats_checklist")
            if isinstance(checklist, str):
                try:
                    checklist = json.loads(checklist)
                except:
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
        
        # Generate apply pack
        pack_data = await apply_pack_generator.generate_apply_pack(
            resume_text=request.resume_text,
            resume_analysis=resume_analysis,
            job_description=job_target.get("description_text", request.job_text or ""),
            job_analysis=job_analysis,
            use_ai=request.use_ai,
        )
        
        # Save apply pack
        apply_pack = await apply_storage.create_apply_pack(
            conn,
            user_id=user_id,
            resume_id=UUID(resume["resume_id"]),
            job_target_id=UUID(job_target["job_target_id"]),
            pack_hash=pack_hash,
            tailored_summary=pack_data.get("tailored_summary"),
            tailored_bullets=pack_data.get("tailored_bullets"),
            cover_note=pack_data.get("cover_note"),
            ats_checklist=pack_data.get("ats_checklist"),
            keyword_coverage=pack_data.get("keyword_coverage"),
        )
        
        # Record usage
        await apply_storage.record_usage(conn, user_id, "apply_pack", UUID(apply_pack["apply_pack_id"]))
        
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
    user_id: UUID = Depends(get_user_id),
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
            except:
                tailored_bullets = []
        elif tailored_bullets is None:
            tailored_bullets = []
        
        ats_checklist = row.get("ats_checklist")
        if isinstance(ats_checklist, str):
            try:
                ats_checklist = json.loads(ats_checklist)
            except:
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
    user_id: UUID = Depends(get_user_id),
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
    user_id: UUID = Depends(get_user_id),
):
    """
    Export apply pack as DOCX file.
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
            except:
                tailored_bullets = []
        elif tailored_bullets is None:
            tailored_bullets = []
        
        # Generate DOCX
        try:
            from backend.app.services import docx_generator
            
            if format == "resume":
                buffer = docx_generator.generate_resume_docx(
                    tailored_summary=apply_pack.get("tailored_summary", ""),
                    tailored_bullets=tailored_bullets,
                    original_resume_text=apply_pack.get("resume_text"),
                )
                filename = "tailored_resume.docx"
            elif format == "cover":
                buffer = docx_generator.generate_cover_note_docx(
                    cover_note=apply_pack.get("cover_note", ""),
                    job_title=apply_pack.get("title"),
                    company_name=apply_pack.get("company"),
                )
                filename = "cover_note.docx"
            else:  # combined
                buffer = docx_generator.generate_combined_docx(
                    tailored_summary=apply_pack.get("tailored_summary", ""),
                    tailored_bullets=tailored_bullets,
                    cover_note=apply_pack.get("cover_note", ""),
                    job_title=apply_pack.get("title"),
                    company_name=apply_pack.get("company"),
                )
                filename = "apply_pack.docx"
            
            # Record usage
            await apply_storage.record_usage(conn, user_id, "docx_export", apply_pack_id)
            
            return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
            
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="DOCX export not available. python-docx package not installed."
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate DOCX: {str(e)}")


@router.post("/application")
async def create_application(
    apply_pack_id: Optional[UUID] = None,
    job_target_id: Optional[UUID] = None,
    status: str = "applied",
    notes: Optional[str] = None,
    reminder_at: Optional[datetime] = None,
    user_id: UUID = Depends(get_user_id),
):
    """Create a tracked application."""
    async with db.connection() as conn:
        # Verify ownership if IDs provided
        if apply_pack_id:
            pack = await conn.fetchrow(
                "SELECT user_id FROM apply_packs WHERE apply_pack_id = $1",
                apply_pack_id
            )
            if not pack or pack["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Apply pack not found")
        
        if job_target_id:
            job = await conn.fetchrow(
                "SELECT user_id FROM job_targets WHERE job_target_id = $1",
                job_target_id
            )
            if job and job["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Job target not found")
        
        application = await apply_storage.create_application(
            conn,
            user_id=user_id,
            apply_pack_id=apply_pack_id,
            job_target_id=job_target_id,
            status=status,
            notes=notes,
            reminder_at=reminder_at,
        )
        
        return {
            "application_id": str(application["application_id"]),
            "status": application["status"],
            "applied_at": application["applied_at"].isoformat() if application.get("applied_at") else None,
        }


@router.get("/application")
async def get_applications(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_user_id),
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
                    "status": app["status"],
                    "title": app.get("title"),
                    "company": app.get("company"),
                    "job_url": app.get("job_url"),
                    "applied_at": app["applied_at"].isoformat() if app.get("applied_at") else None,
                    "notes": app.get("notes"),
                    "reminder_at": app["reminder_at"].isoformat() if app.get("reminder_at") else None,
                }
                for app in applications
            ],
            "total": len(applications),
        }


@router.put("/application/{application_id}")
async def update_application(
    application_id: UUID,
    status: Optional[str] = None,
    notes: Optional[str] = None,
    reminder_at: Optional[datetime] = None,
    user_id: UUID = Depends(get_user_id),
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
        
        if status is not None:
            updates.append(f"status = ${param_idx}")
            values.append(status)
            param_idx += 1
        if notes is not None:
            updates.append(f"notes = ${param_idx}")
            values.append(notes)
            param_idx += 1
        if reminder_at is not None:
            updates.append(f"reminder_at = ${param_idx}")
            values.append(reminder_at)
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
        }


@router.get("/quota")
async def get_quota(
    user_id: UUID = Depends(get_user_id),
):
    """Get user's current quota status."""
    async with db.connection() as conn:
        user = await apply_storage.get_user(conn, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        apply_pack_quota = await apply_storage.check_user_quota(conn, user_id, "apply_pack")
        docx_quota = await apply_storage.check_user_quota(conn, user_id, "docx_export")
        
        return {
            "plan": user.get("plan", "free"),
            "apply_packs": apply_pack_quota,
            "docx_export": docx_quota,
        }
