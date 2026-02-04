"""
Profile API (authenticated).

Provides profile CRUD and resume management for personalization.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID
import hashlib
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.core.auth import AuthUser, get_current_user
from backend.app.storage import apply_storage
from backend.app.services import resume_parser, resume_analyzer


router = APIRouter(prefix="/profile", tags=["profile"])

try:
    import multipart  # type: ignore  # noqa: F401
    _HAS_MULTIPART = True
except Exception:
    _HAS_MULTIPART = False


class ProfileUpsertRequest(BaseModel):
    headline: Optional[str] = None
    location: Optional[str] = None
    desired_roles: Optional[list[str]] = None
    work_authorization: Optional[str] = None
    remote_preferences: Optional[str] = None
    salary_expectations: Optional[dict] = None
    skills: Optional[list[str]] = None
    education: Optional[dict] = None
    certifications: Optional[list[str]] = None
    projects: Optional[dict] = None
    interests: Optional[list[str]] = None
    links: Optional[dict] = None
    primary_resume_id: Optional[UUID] = None


class ResumeTextRequest(BaseModel):
    resume_text: str
    proof_points: Optional[str] = None
    use_ai: bool = True


class SetPrimaryResumeRequest(BaseModel):
    resume_id: UUID


def _hash_profile(payload: dict[str, Any]) -> str:
    stable = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


@router.get("")
async def get_profile(user: AuthUser = Depends(get_current_user)):
    async with db.connection() as conn:
        # Ensure user exists
        await conn.execute(
            """
            INSERT INTO users (user_id, email, plan)
            VALUES ($1, $2, 'free')
            ON CONFLICT (user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
            """,
            user.user_id,
            user.email,
        )

        profile = await apply_storage.get_user_profile(conn, user.user_id)
        resumes = await apply_storage.list_resume_versions(conn, user.user_id, limit=25)

        return {
            "user_id": str(user.user_id),
            "email": user.email,
            "profile": profile,
            "resume_versions": resumes,
        }


@router.put("")
async def upsert_profile(request: ProfileUpsertRequest, user: AuthUser = Depends(get_current_user)):
    payload = request.model_dump(exclude_unset=True)
    payload["profile_hash"] = _hash_profile(payload)

    async with db.connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, email, plan)
            VALUES ($1, $2, 'free')
            ON CONFLICT (user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
            """,
            user.user_id,
            user.email,
        )
        row = await apply_storage.upsert_user_profile(conn, user.user_id, payload)
        return {"profile": row}


@router.post("/resume/text")
async def create_resume_from_text(request: ResumeTextRequest, user: AuthUser = Depends(get_current_user)):
    resume_text = (request.resume_text or "").strip()
    if not resume_text:
        raise HTTPException(status_code=400, detail="resume_text is required")

    analysis = await resume_analyzer.analyze_resume(resume_text, use_ai=request.use_ai)

    async with db.connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, email, plan)
            VALUES ($1, $2, 'free')
            ON CONFLICT (user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
            """,
            user.user_id,
            user.email,
        )
        resume = await apply_storage.create_resume_version(
            conn,
            user_id=user.user_id,
            resume_text=resume_text,
            proof_points=request.proof_points,
            extracted_skills={"skills": analysis.get("skills", [])},
            extracted_seniority=analysis.get("seniority"),
            extracted_bullets=analysis.get("bullets"),
        )
        return {"resume": resume, "analysis": analysis}


if _HAS_MULTIPART:
    @router.post("/resume/upload")
    async def upload_resume(file: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
        if not file.filename:
            raise HTTPException(status_code=400, detail="filename is required")

        content = await file.read()
        parsed = await resume_parser.parse_resume_file(content, file.filename)
        if parsed.get("error"):
            raise HTTPException(status_code=400, detail=parsed["error"])

        resume_text = (parsed.get("text") or "").strip()
        if not resume_text:
            raise HTTPException(status_code=400, detail="Could not extract text from resume")

        analysis = await resume_analyzer.analyze_resume(resume_text, use_ai=True)

        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, email, plan)
                VALUES ($1, $2, 'free')
                ON CONFLICT (user_id)
                DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
                """,
                user.user_id,
                user.email,
            )
            resume = await apply_storage.create_resume_version(
                conn,
                user_id=user.user_id,
                resume_text=resume_text,
                proof_points=None,
                extracted_skills={"skills": analysis.get("skills", [])},
                extracted_seniority=analysis.get("seniority"),
                extracted_bullets=analysis.get("bullets"),
            )
            return {"resume": resume, "analysis": analysis}
else:
    @router.post("/resume/upload")
    async def upload_resume_disabled(user: AuthUser = Depends(get_current_user)):
        raise HTTPException(
            status_code=500,
            detail='Resume upload requires "python-multipart" to be installed on the server.',
        )


@router.get("/resume/{resume_id}")
async def get_resume(resume_id: UUID, user: AuthUser = Depends(get_current_user)):
    async with db.connection() as conn:
        resume = await apply_storage.get_resume_version(conn, user.user_id, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        return {"resume": resume}


@router.put("/resume/primary")
async def set_primary_resume(request: SetPrimaryResumeRequest, user: AuthUser = Depends(get_current_user)):
    async with db.connection() as conn:
        resume = await apply_storage.get_resume_version(conn, user.user_id, request.resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        profile = await apply_storage.set_primary_resume(conn, user.user_id, request.resume_id)
        return {"profile": profile}

