"""
Job listing API endpoints.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import db

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ==================== Schemas ====================

class JobResponse(BaseModel):
    """Job response schema."""

    job_id: str
    title: str
    company: str
    location_raw: str
    country: Optional[str] = None
    city: Optional[str] = None
    remote_type: str
    employment_types: List[str] = []
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    job_url: str
    apply_url: Optional[str] = None
    description_text: Optional[str] = None
    company_website: Optional[str] = None
    linkedin_url: Optional[str] = None
    tags: List[str] = []
    source: str
    posted_at: Optional[datetime] = None
    first_seen_at: datetime
    last_seen_at: datetime

    # AI fields
    ai_score: Optional[float] = None
    ai_reasons: Optional[str] = None
    ai_seniority: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_requirements: Optional[str] = None
    ai_tech_stack: Optional[str] = None
    ai_flags: List[str] = []


class JobListResponse(BaseModel):
    """Paginated job list response."""

    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class JobDetailResponse(JobResponse):
    """Full job detail with description."""

    description_text: str = ""
    emails: List[str] = []
    ai_company_summary: Optional[str] = None


# ==================== Endpoints ====================

@router.get("", response_model=JobListResponse)
async def list_jobs(
    q: Optional[str] = Query(None, description="Search query"),
    location: Optional[str] = Query(None, description="Location filter"),
    remote: Optional[str] = Query(None, description="Remote type: remote, hybrid, onsite"),
    employment: Optional[str] = Query(None, description="Employment type: full_time, contract, etc."),
    source: Optional[str] = Query(None, description="Source filter"),
    posted_since: Optional[int] = Query(None, description="Posted within N days"),
    min_score: Optional[float] = Query(None, description="Minimum AI score (0-100)"),
    sort: str = Query("ai_score", description="Sort by: ai_score, posted_at, first_seen_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    settings: Settings = Depends(get_settings),
):
    """
    List jobs with filtering and pagination.
    """
    if settings.use_sqlite:
        return await _list_jobs_sqlite(
            q, location, remote, employment, source, posted_since,
            min_score, sort, page, page_size, settings
        )

    return await _list_jobs_postgres(
        q, location, remote, employment, source, posted_since,
        min_score, sort, page, page_size, settings
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
):
    """
    Get full job details by ID.
    """
    if settings.use_sqlite:
        return await _get_job_sqlite(job_id, settings)

    return await _get_job_postgres(job_id)


# ==================== SQLite Implementation ====================

async def _list_jobs_sqlite(
    q, location, remote, employment, source, posted_since,
    min_score, sort, page, page_size, settings
) -> JobListResponse:
    """List jobs from SQLite (local dev)."""
    import sqlite3
    import json

    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row

    # Build query
    where_clauses = ["1=1"]
    params = []

    if q:
        where_clauses.append("(title LIKE ? OR company LIKE ? OR description_text LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    if location:
        where_clauses.append("location_raw LIKE ?")
        params.append(f"%{location}%")

    if remote:
        where_clauses.append("remote_type = ?")
        params.append(remote)

    if employment:
        where_clauses.append("employment_types LIKE ?")
        params.append(f"%{employment}%")

    if source:
        where_clauses.append("source = ?")
        params.append(source)

    if posted_since:
        since_date = (datetime.utcnow() - timedelta(days=posted_since)).isoformat()
        where_clauses.append("(posted_at >= ? OR first_seen_at >= ?)")
        params.extend([since_date, since_date])

    if min_score is not None:
        where_clauses.append("ai_score >= ?")
        params.append(min_score)

    where_sql = " AND ".join(where_clauses)

    # Sort
    sort_map = {
        "ai_score": "COALESCE(ai_score, 0) DESC",
        "posted_at": "posted_at DESC NULLS LAST",
        "first_seen_at": "first_seen_at DESC",
    }
    order_sql = sort_map.get(sort, "COALESCE(ai_score, 0) DESC")

    # Count
    count_sql = f"SELECT COUNT(*) FROM jobs WHERE {where_sql}"
    total = conn.execute(count_sql, params).fetchone()[0]

    # Fetch
    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT * FROM jobs
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])
    rows = conn.execute(query_sql, params).fetchall()

    conn.close()

    jobs = [_row_to_job_response(dict(row)) for row in rows]

    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(jobs)) < total,
    )


async def _get_job_sqlite(job_id: str, settings) -> JobDetailResponse:
    """Get job from SQLite."""
    import sqlite3

    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row

    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return _row_to_job_detail(dict(row))


# ==================== Postgres Implementation ====================

async def _list_jobs_postgres(
    q, location, remote, employment, source, posted_since,
    min_score, sort, page, page_size, settings
) -> JobListResponse:
    """List jobs from Postgres."""
    where_clauses = ["1=1"]
    params = []
    param_idx = 1

    if q:
        where_clauses.append(f"(title ILIKE ${param_idx} OR company ILIKE ${param_idx+1} OR description_text ILIKE ${param_idx+2})")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        param_idx += 3

    if location:
        where_clauses.append(f"location_raw ILIKE ${param_idx}")
        params.append(f"%{location}%")
        param_idx += 1

    if remote:
        where_clauses.append(f"remote_type = ${param_idx}")
        params.append(remote)
        param_idx += 1

    if employment:
        where_clauses.append(f"${param_idx} = ANY(employment_types)")
        params.append(employment)
        param_idx += 1

    if source:
        where_clauses.append(f"source = ${param_idx}")
        params.append(source)
        param_idx += 1

    if posted_since:
        since_date = datetime.utcnow() - timedelta(days=posted_since)
        where_clauses.append(f"(posted_at >= ${param_idx} OR first_seen_at >= ${param_idx})")
        params.append(since_date)
        param_idx += 1

    if min_score is not None:
        where_clauses.append(f"ai_score >= ${param_idx}")
        params.append(min_score)
        param_idx += 1

    where_sql = " AND ".join(where_clauses)

    sort_map = {
        "ai_score": "COALESCE(ai_score, 0) DESC",
        "posted_at": "posted_at DESC NULLS LAST",
        "first_seen_at": "first_seen_at DESC",
    }
    order_sql = sort_map.get(sort, "COALESCE(ai_score, 0) DESC")

    async with db.connection() as conn:
        # Count
        count_sql = f"SELECT COUNT(*) FROM jobs WHERE {where_sql}"
        total = await conn.fetchval(count_sql, *params)

        # Fetch
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT * FROM jobs
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ${param_idx} OFFSET ${param_idx+1}
        """
        params.extend([page_size, offset])
        rows = await conn.fetch(query_sql, *params)

    jobs = [_record_to_job_response(row) for row in rows]

    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(jobs)) < total,
    )


async def _get_job_postgres(job_id: str) -> JobDetailResponse:
    """Get job from Postgres."""
    async with db.connection() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs WHERE job_id = $1", job_id)

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return _record_to_job_detail(row)


# ==================== Helpers ====================

def _parse_json_field(val, default=None):
    """Parse JSON field from SQLite."""
    import json
    if not val:
        return default or []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default or []


def _row_to_job_response(row: dict) -> JobResponse:
    """Convert SQLite row to JobResponse."""
    return JobResponse(
        job_id=row["job_id"],
        title=row["title"],
        company=row["company"],
        location_raw=row.get("location_raw", ""),
        country=row.get("country"),
        city=row.get("city"),
        remote_type=row.get("remote_type", "unknown"),
        employment_types=_parse_json_field(row.get("employment_types")),
        salary_min=row.get("salary_min"),
        salary_max=row.get("salary_max"),
        salary_currency=row.get("salary_currency"),
        job_url=row.get("job_url", ""),
        apply_url=row.get("apply_url"),
        company_website=row.get("company_website"),
        linkedin_url=row.get("linkedin_url"),
        tags=_parse_json_field(row.get("tags")),
        source=row.get("source", ""),
        posted_at=row.get("posted_at"),
        first_seen_at=row.get("first_seen_at"),
        last_seen_at=row.get("last_seen_at"),
        ai_score=row.get("ai_score"),
        ai_reasons=row.get("ai_reasons"),
        ai_seniority=row.get("ai_seniority"),
        ai_summary=row.get("ai_summary"),
        ai_requirements=row.get("ai_requirements"),
        ai_tech_stack=row.get("ai_tech_stack"),
        ai_flags=_parse_json_field(row.get("ai_flags")),
    )


def _row_to_job_detail(row: dict) -> JobDetailResponse:
    """Convert SQLite row to JobDetailResponse."""
    base = _row_to_job_response(row)
    return JobDetailResponse(
        **base.model_dump(),
        description_text=row.get("description_text", ""),
        emails=_parse_json_field(row.get("emails")),
        ai_company_summary=row.get("ai_company_summary"),
    )


def _record_to_job_response(row) -> JobResponse:
    """Convert asyncpg Record to JobResponse."""
    return JobResponse(
        job_id=row["job_id"],
        title=row["title"],
        company=row["company"],
        location_raw=row.get("location_raw", ""),
        country=row.get("country"),
        city=row.get("city"),
        remote_type=row.get("remote_type", "unknown"),
        employment_types=row.get("employment_types") or [],
        salary_min=row.get("salary_min"),
        salary_max=row.get("salary_max"),
        salary_currency=row.get("salary_currency"),
        job_url=row.get("job_url", ""),
        apply_url=row.get("apply_url"),
        company_website=row.get("company_website"),
        linkedin_url=row.get("linkedin_url"),
        tags=row.get("tags") or [],
        source=row.get("source", ""),
        posted_at=row.get("posted_at"),
        first_seen_at=row.get("first_seen_at"),
        last_seen_at=row.get("last_seen_at"),
        ai_score=row.get("ai_score"),
        ai_reasons=row.get("ai_reasons"),
        ai_seniority=row.get("ai_seniority"),
        ai_summary=row.get("ai_summary"),
        ai_requirements=row.get("ai_requirements"),
        ai_tech_stack=row.get("ai_tech_stack"),
        ai_flags=row.get("ai_flags") or [],
    )


def _record_to_job_detail(row) -> JobDetailResponse:
    """Convert asyncpg Record to JobDetailResponse."""
    base = _record_to_job_response(row)
    return JobDetailResponse(
        **base.model_dump(),
        description_text=row.get("description_text", ""),
        emails=row.get("emails") or [],
        ai_company_summary=row.get("ai_company_summary"),
    )
