"""
Run status endpoints (scrape runs).

Runs are stored in Postgres `runs` table.
"""

from datetime import datetime
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import db

router = APIRouter(tags=["runs"])


class RunResponse(BaseModel):
    run_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    jobs_collected: int = 0
    jobs_new: int = 0
    jobs_updated: int = 0
    jobs_filtered: int = 0
    errors: int = 0
    sources: Optional[str] = None
    criteria: Optional[Dict[str, Any]] = None

    @property
    def status(self) -> str:
        return "finished" if self.finished_at else "running"


@router.get("/runs/latest", response_model=RunResponse)
async def get_latest_run(settings: Settings = Depends(get_settings)):
    """Get the most recent run (Postgres)."""
    if settings.use_sqlite:
        # Avoid crashing in local dev when Postgres pool isn't configured.
        raise HTTPException(status_code=404, detail="Runs endpoint not available in SQLite mode")
    async with db.connection() as conn:
        row = await conn.fetchrow("SELECT * FROM runs ORDER BY run_id DESC LIMIT 1")

    if not row:
        raise HTTPException(status_code=404, detail="No runs found")

    data = dict(row)
    crit = data.get("criteria")
    if isinstance(crit, str):
        try:
            data["criteria"] = json.loads(crit)
        except Exception:
            data["criteria"] = None
    return RunResponse(**data)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, settings: Settings = Depends(get_settings)):
    """Get a run by ID (Postgres)."""
    if settings.use_sqlite:
        raise HTTPException(status_code=404, detail="Runs endpoint not available in SQLite mode")
    try:
        async with db.connection() as conn:
            # First check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'runs'
                )
            """)
            if not table_exists:
                raise HTTPException(status_code=500, detail="Runs table does not exist. Schema may not be initialized.")
            
            row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
            
            if not row:
                # Debug: check if any runs exist
                count = await conn.fetchval("SELECT COUNT(*) FROM runs")
                raise HTTPException(
                    status_code=404, 
                    detail=f"Run {run_id} not found. Total runs in DB: {count}"
                )

            data = dict(row)
            crit = data.get("criteria")
            if isinstance(crit, str):
                try:
                    data["criteria"] = json.loads(crit)
                except Exception:
                    data["criteria"] = None
            return RunResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

