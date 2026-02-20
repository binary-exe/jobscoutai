"""
Paddle payment webhook handler for Apply Workspace.

Handles subscription events from Paddle.
Checkout requires authenticated Supabase user (no anonymous users for billing).
"""

import hmac
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Header, Depends, Query
from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.core.database import db
from backend.app.core.auth import get_current_user, AuthUser
from backend.app.storage import apply_storage

router = APIRouter(prefix="/paddle", tags=["paddle"])


class PaddleWebhook(BaseModel):
    """Paddle webhook event."""
    event_type: str
    event_id: str
    data: Dict[str, Any]


def verify_paddle_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Paddle webhook signature."""
    expected_signature = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


PLAN_CREDITS = {
    "weekly_standard": 200,
    "weekly_pro": 500,
    "monthly_standard": 1200,
    "monthly_pro": 2500,
    "weekly_sprint": 300,
    "monthly_power": 3000,
    "annual_pro": 1500,
    "annual_power": 3000,
}

ANNUAL_PLANS = {"annual_pro", "annual_power"}
TOPUP_CREDITS = {"topup_20": 200}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_price_id(data: Dict[str, Any]) -> Optional[str]:
    price_id = data.get("price_id") or data.get("price")
    if isinstance(price_id, dict):
        price_id = price_id.get("id") or price_id.get("price_id")
    if isinstance(price_id, str):
        return price_id
    items = data.get("items") or data.get("line_items") or []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = item.get("price_id") or item.get("price")
            if isinstance(pid, dict):
                pid = pid.get("id") or pid.get("price_id")
            if isinstance(pid, str):
                return pid
    return None


def _extract_custom_plan(data: Dict[str, Any]) -> Optional[str]:
    custom_data = data.get("custom_data") or {}
    if isinstance(custom_data, str):
        try:
            custom_data = json.loads(custom_data)
        except Exception:
            custom_data = {}
    if isinstance(custom_data, dict):
        plan = custom_data.get("plan")
        if isinstance(plan, str):
            return plan.strip().lower()
    return None


def _plan_from_price_id(price_id: Optional[str], settings) -> Optional[str]:
    if not price_id:
        return None
    mapping = {
        settings.paddle_price_id_weekly_standard: "weekly_standard",
        settings.paddle_price_id_weekly_pro: "weekly_pro",
        settings.paddle_price_id_monthly_standard: "monthly_standard",
        settings.paddle_price_id_weekly_sprint: "weekly_sprint",
        settings.paddle_price_id_monthly_pro: "monthly_pro",
        settings.paddle_price_id_monthly_power: "monthly_power",
        settings.paddle_price_id_annual_pro: "annual_pro",
        settings.paddle_price_id_annual_power: "annual_power",
    }
    plan = mapping.get(price_id)
    if plan:
        return plan
    if settings.paddle_product_id and price_id == settings.paddle_product_id:
        return "monthly_standard"
    return None


def _topup_from_price_id(price_id: Optional[str], settings) -> Optional[str]:
    if not price_id:
        return None
    mapping = {
        settings.paddle_price_id_topup_20: "topup_20",
    }
    return mapping.get(price_id)


def _price_id_for_plan(plan: Optional[str], settings) -> Optional[str]:
    if not plan:
        return settings.paddle_product_id or settings.paddle_vendor_id
    plan_norm = plan.strip().lower()
    mapping = {
        "weekly_standard": settings.paddle_price_id_weekly_standard,
        "weekly_pro": settings.paddle_price_id_weekly_pro,
        "monthly_standard": settings.paddle_price_id_monthly_standard,
        "weekly_sprint": settings.paddle_price_id_weekly_sprint,
        "monthly_pro": settings.paddle_price_id_monthly_pro,
        "monthly_power": settings.paddle_price_id_monthly_power,
        "annual_pro": settings.paddle_price_id_annual_pro,
        "annual_power": settings.paddle_price_id_annual_power,
        "topup_20": settings.paddle_price_id_topup_20,
    }
    return mapping.get(plan_norm)


async def _grant_plan_credits(
    conn,
    *,
    user_id,
    plan: str,
    event_id: str,
):
    credits = PLAN_CREDITS.get(plan)
    if not credits:
        return
    now = _now_utc()
    if plan in ANNUAL_PLANS:
        for idx in range(12):
            available_at = now + timedelta(days=30 * idx)
            await apply_storage.grant_credits(
                conn,
                user_id=user_id,
                amount=credits,
                reason="plan_grant",
                idempotency_key=f"{event_id}:annual:{idx}",
                metadata={"plan": plan, "cycle_index": idx},
                available_at=available_at,
            )
    else:
        await apply_storage.grant_credits(
            conn,
            user_id=user_id,
            amount=credits,
            reason="plan_grant",
            idempotency_key=f"{event_id}:{plan}",
            metadata={"plan": plan},
            available_at=now,
        )


async def _grant_topup_credits(
    conn,
    *,
    user_id,
    topup_key: str,
    event_id: str,
):
    credits = TOPUP_CREDITS.get(topup_key)
    if not credits:
        return
    await apply_storage.grant_credits(
        conn,
        user_id=user_id,
        amount=credits,
        reason="topup",
        idempotency_key=f"{event_id}:{topup_key}",
        metadata={"topup": topup_key},
        available_at=_now_utc(),
    )


@router.post("/webhook")
async def handle_paddle_webhook(
    request: Request,
    p_signature: str = Header(..., alias="p-signature"),
):
    """
    Handle Paddle webhook events.
    
    Events handled:
    - subscription.created: Upgrade user to paid
    - subscription.updated: Update subscription status
    - subscription.cancelled: Mark for downgrade at period end
    - payment.succeeded: Extend subscription
    - payment.failed: Handle failed payment
    """
    settings = get_settings()
    
    if not settings.paddle_webhook_secret:
        raise HTTPException(status_code=500, detail="Paddle webhook secret not configured")
    
    # Get request body
    body = await request.body()
    
    # Verify signature
    if not verify_paddle_signature(body, p_signature, settings.paddle_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    try:
        event = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    event_type = event.get("event_type")
    event_id = event.get("event_id")
    event_data = event.get("data", {})
    
    if not event_type:
        raise HTTPException(status_code=400, detail="Missing event_type")
    
    async with db.connection() as conn:
        # Handle different event types
        if event_type == "subscription.created":
            await _handle_subscription_created(conn, event_data, event_id=event_id)
        elif event_type == "subscription.updated":
            await _handle_subscription_updated(conn, event_data, event_id=event_id)
        elif event_type == "subscription.cancelled":
            await _handle_subscription_cancelled(conn, event_data, event_id=event_id)
        elif event_type == "payment.succeeded":
            await _handle_payment_succeeded(conn, event_data, event_id=event_id)
        elif event_type == "payment.failed":
            await _handle_payment_failed(conn, event_data, event_id=event_id)
        elif event_type == "transaction.completed":
            await _handle_transaction_completed(conn, event_data, event_id=event_id)
        else:
            # Unknown event type - log but don't fail
            print(f"Unknown Paddle event type: {event_type}")
    
    return {"status": "ok"}


async def _find_user_from_webhook(conn, data: Dict[str, Any]):
    """
    Find user from webhook data using multiple strategies.
    
    Priority order:
    1. custom_data.user_id (most reliable - set during checkout)
    2. paddle_customer_id
    3. subscription_id
    """
    # Strategy 1: custom_data.user_id
    custom_data = data.get("custom_data") or {}
    if isinstance(custom_data, str):
        try:
            custom_data = json.loads(custom_data)
        except Exception:
            custom_data = {}
    
    custom_user_id = custom_data.get("user_id")
    if custom_user_id:
        try:
            user_uuid = UUID(custom_user_id)
            user = await conn.fetchrow(
                "SELECT user_id FROM users WHERE user_id = $1",
                user_uuid
            )
            if user:
                return user
        except (ValueError, TypeError):
            pass
    
    # Strategy 2: paddle_customer_id
    customer_id = data.get("customer_id")
    if customer_id:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE paddle_customer_id = $1",
            str(customer_id)
        )
        if user:
            return user
    
    # Strategy 3: subscription_id
    subscription_id = data.get("id") or data.get("subscription_id")
    if subscription_id:
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE subscription_id = $1",
            str(subscription_id)
        )
        if user:
            return user
    
    return None


async def _handle_subscription_created(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle subscription.created event."""
    customer_id = data.get("customer_id")
    subscription_id = data.get("id")
    settings = get_settings()
    
    if not subscription_id:
        print(f"Missing subscription_id in subscription.created: {data}")
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for subscription.created: customer_id={customer_id}, custom_data={data.get('custom_data')}")
        return
    
    price_id = _extract_price_id(data)
    plan_key = _plan_from_price_id(price_id, settings) or _extract_custom_plan(data) or "monthly_standard"
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan=plan_key,
        subscription_id=str(subscription_id),
        paddle_customer_id=str(customer_id) if customer_id else None,
        subscription_status="active",
    )
    await _grant_plan_credits(
        conn,
        user_id=user["user_id"],
        plan=plan_key,
        event_id=str(event_id or subscription_id),
    )

    # Award referral credit to referrer when referee becomes paid
    try:
        full_user = await apply_storage.get_user(conn, user["user_id"])
        referrer_id = full_user.get("referred_by") if full_user else None
        if referrer_id:
            await apply_storage.complete_referral_for_paid_referee(
                conn,
                referrer_id=referrer_id,
                referee_id=user["user_id"],
            )
    except Exception:
        pass
    
    print(f"Upgraded user {user['user_id']} to {plan_key} plan")


async def _handle_subscription_updated(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle subscription.updated event."""
    subscription_id = data.get("id")
    status = data.get("status")
    settings = get_settings()
    
    if not subscription_id:
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for subscription.updated: subscription_id={subscription_id}")
        return
    
    price_id = _extract_price_id(data)
    plan_key = _plan_from_price_id(price_id, settings) or _extract_custom_plan(data)
    if not plan_key:
        existing = await apply_storage.get_user(conn, user["user_id"])
        plan_key = (existing or {}).get("plan") or "monthly_standard"
    if status in ("active", "past_due", "cancelled"):
        new_plan = plan_key
    else:
        new_plan = "free"
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan=new_plan,
        subscription_status=status,
    )
    
    print(f"Updated subscription {subscription_id} status to {status}")


async def _handle_subscription_cancelled(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle subscription.cancelled event."""
    subscription_id = data.get("id")
    cancellation_effective_date = data.get("cancellation_effective_date")
    settings = get_settings()
    
    if not subscription_id:
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for subscription.cancelled: subscription_id={subscription_id}")
        return
    
    # Mark for downgrade at period end
    from datetime import datetime
    ends_at = None
    if cancellation_effective_date:
        try:
            ends_at = datetime.fromisoformat(cancellation_effective_date.replace("Z", "+00:00"))
        except Exception:
            pass
    
    price_id = _extract_price_id(data)
    plan_key = _plan_from_price_id(price_id, settings) or _extract_custom_plan(data)
    if not plan_key:
        existing = await apply_storage.get_user(conn, user["user_id"])
        plan_key = (existing or {}).get("plan") or "monthly_standard"
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan=plan_key,  # Keep paid until period end
        subscription_status="cancelled",
        subscription_ends_at=ends_at,
    )
    if ends_at:
        await apply_storage.set_credit_expiry_for_subscription(
            conn,
            user_id=user["user_id"],
            expires_at=ends_at,
        )
    
    print(f"Cancelled subscription {subscription_id}, effective: {ends_at}")


async def _handle_payment_succeeded(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle payment.succeeded event."""
    subscription_id = data.get("subscription_id")
    settings = get_settings()
    
    price_id = _extract_price_id(data)
    topup_key = _topup_from_price_id(price_id, settings)
    if topup_key:
        user = await _find_user_from_webhook(conn, data)
        if not user:
            print(f"User not found for payment.succeeded topup: price_id={price_id}")
            return
        await _grant_topup_credits(
            conn,
            user_id=user["user_id"],
            topup_key=topup_key,
            event_id=str(event_id or price_id),
        )
        print(f"Granted topup credits ({topup_key}) to user {user['user_id']}")
        return

    if not subscription_id:
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for payment.succeeded: subscription_id={subscription_id}")
        return
    
    price_id = _extract_price_id(data)
    plan_key = _plan_from_price_id(price_id, settings) or _extract_custom_plan(data)
    if not plan_key:
        existing = await apply_storage.get_user(conn, user["user_id"])
        plan_key = (existing or {}).get("plan") or "monthly_standard"
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan=plan_key,
        subscription_status="active",
    )
    await _grant_plan_credits(
        conn,
        user_id=user["user_id"],
        plan=plan_key,
        event_id=str(event_id or subscription_id),
    )

    # Award referral credit to referrer when referee becomes paid
    try:
        full_user = await apply_storage.get_user(conn, user["user_id"])
        referrer_id = full_user.get("referred_by") if full_user else None
        if referrer_id:
            await apply_storage.complete_referral_for_paid_referee(
                conn,
                referrer_id=referrer_id,
                referee_id=user["user_id"],
            )
    except Exception:
        pass
    
    print(f"Payment succeeded for subscription {subscription_id}")


async def _handle_payment_failed(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle payment.failed event."""
    subscription_id = data.get("subscription_id")
    
    if not subscription_id:
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for payment.failed: subscription_id={subscription_id}")
        return
    
    settings = get_settings()
    price_id = _extract_price_id(data)
    plan_key = _plan_from_price_id(price_id, settings) or _extract_custom_plan(data)
    if not plan_key:
        existing = await apply_storage.get_user(conn, user["user_id"])
        plan_key = (existing or {}).get("plan") or "monthly_standard"
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan=plan_key,
        subscription_status="past_due",
    )
    
    print(f"Payment failed for subscription {subscription_id}")


async def _handle_transaction_completed(conn, data: Dict[str, Any], *, event_id: Optional[str] = None):
    """Handle transaction.completed events (one-time purchases)."""
    settings = get_settings()
    price_id = _extract_price_id(data)
    topup_key = _topup_from_price_id(price_id, settings)
    if not topup_key:
        return
    user = await _find_user_from_webhook(conn, data)
    if not user:
        print(f"User not found for transaction.completed topup: price_id={price_id}")
        return
    await _grant_topup_credits(
        conn,
        user_id=user["user_id"],
        topup_key=topup_key,
        event_id=str(event_id or price_id),
    )
    print(f"Granted topup credits ({topup_key}) to user {user['user_id']}")


@router.get("/checkout-url")
async def get_checkout_url(
    auth_user: AuthUser = Depends(get_current_user),
    plan: Optional[str] = Query(None, description="Plan key (weekly_standard|weekly_pro|monthly_standard|monthly_pro)"),
):
    """
    Get Paddle checkout URL for authenticated user.
    
    Creates a checkout link via Paddle API for a selected subscription plan.
    Returns checkout URL that user can redirect to.
    
    REQUIRES AUTHENTICATION: Only authenticated Supabase users can start checkout.
    This ensures billing is tied to a verified identity.
    
    Note: Requires Paddle product and price setup in Paddle dashboard.
    Set JOBSCOUT_PADDLE_PRODUCT_ID environment variable with your product ID.
    """
    settings = get_settings()
    
    if not settings.paddle_api_key:
        raise HTTPException(status_code=500, detail="Paddle API key not configured")
    
    # Get or create user record with Supabase UUID
    user_uuid = auth_user.user_id
    async with db.connection() as conn:
        # Ensure user exists in our DB
        await conn.execute(
            """
            INSERT INTO users (user_id, email, plan)
            VALUES ($1, $2, 'free')
            ON CONFLICT (user_id)
            DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email), updated_at = NOW()
            """,
            user_uuid,
            auth_user.email,
        )
        
        user = await apply_storage.get_user(conn, user_uuid)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user record")
        
        is_topup = (plan or "").strip().lower().startswith("topup_") if plan else False
        # Check if user already has a subscription
        if not is_topup and apply_storage.is_paid_user(user) and user.get("subscription_status") == "active":
            raise HTTPException(
                status_code=400,
                detail="User already has an active subscription"
            )
        
        # Determine API base URL based on environment
        if settings.paddle_environment == "production":
            api_base = "https://api.paddle.com"
        else:
            api_base = "https://sandbox-api.paddle.com"
        
        try:
            import httpx
            
            # Get or create Paddle customer ID
            paddle_customer_id = user.get("paddle_customer_id")
            
            if not paddle_customer_id:
                # Create customer in Paddle
                customer_email = user.get("email") or f"user_{str(user_uuid)[:8]}@jobscout.ai"
                customer_response = await httpx.AsyncClient().post(
                    f"{api_base}/customers",
                    headers={
                        "Authorization": f"Bearer {settings.paddle_api_key}",
                        "Content-Type": "application/json",
                        "Paddle-Version": "1",
                    },
                    json={
                        "email": customer_email,
                        "name": f"JobScout User {str(user_uuid)[:8]}",
                    },
                    timeout=10.0,
                )
                
                if customer_response.status_code in [200, 201]:
                    customer_data = customer_response.json()
                    paddle_customer_id = customer_data.get("data", {}).get("id")
                    
                    # Store customer ID in database
                    await apply_storage.update_user_plan(
                        conn,
                        user_id=user_uuid,
                        paddle_customer_id=str(paddle_customer_id),
                    )
                else:
                    # If customer creation fails, log and continue
                    print(f"Failed to create Paddle customer: {customer_response.status_code} - {customer_response.text}")
            
            # Get price ID from settings (per plan)
            price_id = _price_id_for_plan(plan, settings)
            if not price_id:
                raise HTTPException(
                    status_code=500,
                    detail="Paddle price ID not configured for selected plan."
                )
            
            # Generate checkout link using Paddle's transaction preview API
            # This creates a checkout link for a subscription
            checkout_data = {
                "items": [
                    {
                        "price_id": price_id,  # This should be your subscription price_id from Paddle
                        "quantity": 1,
                    }
                ],
                "customer_id": paddle_customer_id,
                "custom_data": {
                    "user_id": str(user_uuid),
                    "plan": plan,
                    "is_topup": bool(is_topup),
                },
            }
            
            # Use Paddle's transaction preview to get checkout URL
            checkout_response = await httpx.AsyncClient().post(
                f"{api_base}/transactions/preview",
                headers={
                    "Authorization": f"Bearer {settings.paddle_api_key}",
                    "Content-Type": "application/json",
                    "Paddle-Version": "1",
                },
                json=checkout_data,
                timeout=10.0,
            )
            
            if checkout_response.status_code in [200, 201]:
                checkout_result = checkout_response.json()
                # Paddle's response structure may vary - check for checkout URL
                checkout_url = (
                    checkout_result.get("data", {}).get("checkout", {}).get("url") or
                    checkout_result.get("data", {}).get("url") or
                    checkout_result.get("url")
                )
                
                if checkout_url:
                    return {
                        "checkout_url": checkout_url,
                        "message": "Redirect user to this URL to complete checkout",
                    }
            
            # Fallback: Use Paddle's hosted checkout page
            base_url = "https://checkout.paddle.com" if settings.paddle_environment == "production" else "https://sandbox-checkout.paddle.com"
            
            # Build checkout URL with customer ID if available
            checkout_params = {
                "product": price_id,
            }
            if paddle_customer_id:
                checkout_params["customer"] = paddle_customer_id
            
            from urllib.parse import urlencode
            checkout_url = f"{base_url}/product/{product_id}?{urlencode(checkout_params)}"
            
            return {
                "checkout_url": checkout_url,
                "message": "Redirect user to this URL to complete checkout",
            }
            
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="httpx library not installed. Install with: pip install httpx"
            )
        except Exception as e:
            # Log error for debugging
            import traceback
            print(f"Paddle checkout error: {e}")
            print(traceback.format_exc())
            
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate checkout URL: {str(e)}"
            )
