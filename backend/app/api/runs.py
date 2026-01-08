"""
Run status endpoints (scrape runs).

Runs are stored in Postgres `runs` table.
"""

from datetime import datetime
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.database import db

router = APIRouter(prefix="/runs", tags=["runs"])


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


@router.get("/latest", response_model=RunResponse)
async def get_latest_run():
    """Get the most recent run (Postgres)."""
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


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: int):
    """Get a run by ID (Postgres)."""
    async with db.connection() as conn:
        row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)

    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    data = dict(row)
    crit = data.get("criteria")
    if isinstance(crit, str):
        try:
            data["criteria"] = json.loads(crit)
        except Exception:
            data["criteria"] = None
    return RunResponse(**data)

