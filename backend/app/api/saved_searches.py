"""
API endpoints for Saved Searches and Job Alerts.

Allows users to:
- Save search filters for quick access
- Set up job alerts (daily/weekly notifications)
- Manage email preferences
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.core.auth import get_current_user, AuthUser

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


# ==================== Request/Response Models ====================

class SavedSearchFilters(BaseModel):
    location: Optional[str] = None
    remote: Optional[str] = None  # remote, hybrid, onsite
    employment: Optional[str] = None  # full-time, part-time, contract
    min_score: Optional[int] = None
    posted_since: Optional[int] = None  # days


class CreateSavedSearchRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[SavedSearchFilters] = None
    notify_frequency: str = "weekly"  # daily, weekly, never


class UpdateSavedSearchRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[SavedSearchFilters] = None
    notify_frequency: Optional[str] = None
    is_active: Optional[bool] = None


class SavedSearchResponse(BaseModel):
    search_id: str
    name: Optional[str]
    query: Optional[str]
    filters: dict
    notify_frequency: str
    is_active: bool
    created_at: datetime


class EmailPreferencesRequest(BaseModel):
    weekly_digest: Optional[bool] = None
    job_alerts: Optional[bool] = None
    marketing: Optional[bool] = None


# ==================== Endpoints ====================

@router.post("")
async def create_saved_search(
    request: CreateSavedSearchRequest,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Create a new saved search with optional job alerts."""
    async with db.connection() as conn:
        # Check max saved searches (limit to 10 for free users)
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM saved_searches WHERE user_id = $1",
            auth_user.user_id
        )
        
        # Get user plan
        user = await conn.fetchrow(
            "SELECT plan FROM users WHERE user_id = $1",
            auth_user.user_id
        )
        plan = user["plan"] if user else "free"
        max_searches = 10 if plan == "free" else 50
        
        if count >= max_searches:
            raise HTTPException(
                status_code=403,
                detail=f"Maximum {max_searches} saved searches allowed on {plan} plan"
            )
        
        # Generate name if not provided
        name = request.name
        if not name:
            if request.query:
                name = f"Search: {request.query[:30]}"
            elif request.filters:
                parts = []
                if request.filters.remote:
                    parts.append(request.filters.remote)
                if request.filters.location:
                    parts.append(request.filters.location)
                name = " ".join(parts) or "My Search"
            else:
                name = "My Search"
        
        # Create saved search
        filters_dict = request.filters.dict() if request.filters else {}
        
        row = await conn.fetchrow(
            """
            INSERT INTO saved_searches (user_id, name, query, filters, notify_frequency)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            auth_user.user_id,
            name,
            request.query,
            filters_dict,
            request.notify_frequency,
        )
        
        return SavedSearchResponse(
            search_id=str(row["search_id"]),
            name=row["name"],
            query=row["query"],
            filters=row["filters"] or {},
            notify_frequency=row["notify_frequency"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@router.get("")
async def list_saved_searches(
    auth_user: AuthUser = Depends(get_current_user),
) -> List[SavedSearchResponse]:
    """List all saved searches for the current user."""
    async with db.connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM saved_searches
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            auth_user.user_id
        )
        
        return [
            SavedSearchResponse(
                search_id=str(row["search_id"]),
                name=row["name"],
                query=row["query"],
                filters=row["filters"] or {},
                notify_frequency=row["notify_frequency"],
                is_active=row["is_active"],
                created_at=row["created_at"],
            )
            for row in rows
        ]


@router.get("/{search_id}")
async def get_saved_search(
    search_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Get a saved search by ID."""
    async with db.connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM saved_searches
            WHERE search_id = $1 AND user_id = $2
            """,
            search_id,
            auth_user.user_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        
        return SavedSearchResponse(
            search_id=str(row["search_id"]),
            name=row["name"],
            query=row["query"],
            filters=row["filters"] or {},
            notify_frequency=row["notify_frequency"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@router.put("/{search_id}")
async def update_saved_search(
    search_id: UUID,
    request: UpdateSavedSearchRequest,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Update a saved search."""
    async with db.connection() as conn:
        # Verify ownership
        existing = await conn.fetchrow(
            "SELECT user_id FROM saved_searches WHERE search_id = $1",
            search_id
        )
        
        if not existing or existing["user_id"] != auth_user.user_id:
            raise HTTPException(status_code=404, detail="Saved search not found")
        
        # Build update query
        updates = []
        values = []
        param_idx = 1
        
        if request.name is not None:
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1
        if request.query is not None:
            updates.append(f"query = ${param_idx}")
            values.append(request.query)
            param_idx += 1
        if request.filters is not None:
            updates.append(f"filters = ${param_idx}")
            values.append(request.filters.dict())
            param_idx += 1
        if request.notify_frequency is not None:
            updates.append(f"notify_frequency = ${param_idx}")
            values.append(request.notify_frequency)
            param_idx += 1
        if request.is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            values.append(request.is_active)
            param_idx += 1
        
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updates.append("updated_at = NOW()")
        values.append(search_id)
        
        query = f"""
            UPDATE saved_searches
            SET {', '.join(updates)}
            WHERE search_id = ${param_idx}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        
        return SavedSearchResponse(
            search_id=str(row["search_id"]),
            name=row["name"],
            query=row["query"],
            filters=row["filters"] or {},
            notify_frequency=row["notify_frequency"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )


@router.delete("/{search_id}")
async def delete_saved_search(
    search_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Delete a saved search."""
    async with db.connection() as conn:
        result = await conn.execute(
            """
            DELETE FROM saved_searches
            WHERE search_id = $1 AND user_id = $2
            """,
            search_id,
            auth_user.user_id
        )
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Saved search not found")
        
        return {"status": "deleted"}


@router.get("/preferences/email")
async def get_email_preferences(
    auth_user: AuthUser = Depends(get_current_user),
):
    """Get user's email preferences."""
    async with db.connection() as conn:
        row = await conn.fetchrow(
            "SELECT email_preferences FROM users WHERE user_id = $1",
            auth_user.user_id
        )
        
        preferences = row["email_preferences"] if row and row["email_preferences"] else {
            "weekly_digest": True,
            "job_alerts": True,
            "marketing": True,
        }
        
        return preferences


@router.put("/preferences/email")
async def update_email_preferences(
    request: EmailPreferencesRequest,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Update user's email preferences."""
    async with db.connection() as conn:
        # Get current preferences
        row = await conn.fetchrow(
            "SELECT email_preferences FROM users WHERE user_id = $1",
            auth_user.user_id
        )
        
        current = row["email_preferences"] if row and row["email_preferences"] else {
            "weekly_digest": True,
            "job_alerts": True,
            "marketing": True,
        }
        
        # Update with new values
        if request.weekly_digest is not None:
            current["weekly_digest"] = request.weekly_digest
        if request.job_alerts is not None:
            current["job_alerts"] = request.job_alerts
        if request.marketing is not None:
            current["marketing"] = request.marketing
        
        await conn.execute(
            "UPDATE users SET email_preferences = $1 WHERE user_id = $2",
            current,
            auth_user.user_id
        )
        
        return current
