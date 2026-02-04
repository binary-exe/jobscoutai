"""
API endpoints for Referral System.

"Give 10 packs, Get 10 packs" - both referrer and referee get 10 Apply Packs
when the referee creates their first Apply Pack.
"""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.app.core.database import db
from backend.app.core.auth import get_current_user, AuthUser
from backend.app.storage import apply_storage

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferralStatsResponse(BaseModel):
    referral_code: str
    referral_link: str
    completed_referrals: int
    pending_referrals: int
    total_packs_earned: int


class ApplyReferralRequest(BaseModel):
    referral_code: str


# ==================== Endpoints ====================

@router.get("/stats")
async def get_referral_stats(
    auth_user: AuthUser = Depends(get_current_user),
) -> ReferralStatsResponse:
    """
    Get user's referral statistics and unique referral link.
    """
    async with db.connection() as conn:
        stats = await apply_storage.get_user_referral_stats(conn, auth_user.user_id)
        
        # Build referral link
        site_url = "https://jobscoutai.vercel.app"  # TODO: Make configurable
        referral_link = f"{site_url}/login?ref={stats['referral_code']}"
        
        return ReferralStatsResponse(
            referral_code=stats["referral_code"],
            referral_link=referral_link,
            completed_referrals=stats["completed_referrals"],
            pending_referrals=stats["pending_referrals"],
            total_packs_earned=stats["total_packs_earned"],
        )


@router.post("/apply")
async def apply_referral_code(
    request: ApplyReferralRequest,
    auth_user: AuthUser = Depends(get_current_user),
):
    """
    Apply a referral code for the current user.
    
    This is called when a user signs up through a referral link.
    The actual pack awards happen when the referee creates their first Apply Pack.
    """
    async with db.connection() as conn:
        try:
            # Check if user already has a referrer
            user = await apply_storage.get_user(conn, auth_user.user_id)
            if user and user.get("referred_by"):
                return {"status": "already_referred", "message": "You have already used a referral code"}
            
            # Verify referral code exists
            referrer = await apply_storage.get_user_by_referral_code(conn, request.referral_code)
            if not referrer:
                raise HTTPException(status_code=404, detail="Invalid referral code")
            
            # Can't refer yourself
            if referrer["user_id"] == auth_user.user_id:
                raise HTTPException(status_code=400, detail="Cannot use your own referral code")
            
            # Mark user as referred (packs awarded on first Apply Pack creation)
            await conn.execute(
                "UPDATE users SET referred_by = $1 WHERE user_id = $2",
                referrer["user_id"], auth_user.user_id
            )
            
            return {
                "status": "applied",
                "message": "Referral code applied! You'll both get 10 free Apply Packs when you create your first Apply Pack.",
            }
        except HTTPException:
            raise
        except Exception:
            # Referral columns might not exist yet (migration not run)
            return {
                "status": "unavailable",
                "message": "Referral system is being set up. Please try again later.",
            }


@router.get("/check/{code}")
async def check_referral_code(code: str):
    """
    Check if a referral code is valid (public endpoint for signup flow).
    """
    try:
        async with db.connection() as conn:
            referrer = await apply_storage.get_user_by_referral_code(conn, code)
            
            if not referrer:
                return {"valid": False}
            
            return {
                "valid": True,
                "referrer_name": referrer.get("email", "").split("@")[0] if referrer.get("email") else "A JobScout user",
            }
    except Exception:
        # Table/column might not exist yet
        return {"valid": False}
