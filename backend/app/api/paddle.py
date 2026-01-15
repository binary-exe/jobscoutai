"""
Paddle payment webhook handler for Apply Workspace.

Handles subscription events from Paddle.
"""

import hmac
import hashlib
import json
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.core.database import db
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
    event_data = event.get("data", {})
    
    if not event_type:
        raise HTTPException(status_code=400, detail="Missing event_type")
    
    async with db.connection() as conn:
        # Handle different event types
        if event_type == "subscription.created":
            await _handle_subscription_created(conn, event_data)
        elif event_type == "subscription.updated":
            await _handle_subscription_updated(conn, event_data)
        elif event_type == "subscription.cancelled":
            await _handle_subscription_cancelled(conn, event_data)
        elif event_type == "payment.succeeded":
            await _handle_payment_succeeded(conn, event_data)
        elif event_type == "payment.failed":
            await _handle_payment_failed(conn, event_data)
        else:
            # Unknown event type - log but don't fail
            print(f"Unknown Paddle event type: {event_type}")
    
    return {"status": "ok"}


async def _handle_subscription_created(conn, data: Dict[str, Any]):
    """Handle subscription.created event."""
    customer_id = data.get("customer_id")
    subscription_id = data.get("id")
    
    if not customer_id or not subscription_id:
        print(f"Missing customer_id or subscription_id in subscription.created: {data}")
        return
    
    # Find user by Paddle customer ID
    user = await conn.fetchrow(
        "SELECT user_id FROM users WHERE paddle_customer_id = $1",
        str(customer_id)
    )
    
    if not user:
        print(f"User not found for customer_id: {customer_id}")
        return
    
    # Upgrade to paid
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid",
        subscription_id=str(subscription_id),
        paddle_customer_id=str(customer_id),
        subscription_status="active",
    )
    
    print(f"Upgraded user {user['user_id']} to paid plan")


async def _handle_subscription_updated(conn, data: Dict[str, Any]):
    """Handle subscription.updated event."""
    subscription_id = data.get("id")
    status = data.get("status")
    customer_id = data.get("customer_id")
    
    if not subscription_id:
        return
    
    # Find user by subscription ID
    user = await conn.fetchrow(
        "SELECT user_id FROM users WHERE subscription_id = $1",
        str(subscription_id)
    )
    
    if not user and customer_id:
        # Try by customer ID
        user = await conn.fetchrow(
            "SELECT user_id FROM users WHERE paddle_customer_id = $1",
            str(customer_id)
        )
    
    if not user:
        print(f"User not found for subscription_id: {subscription_id}")
        return
    
    # Update subscription status
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid" if status == "active" else "free",
        subscription_status=status,
    )
    
    print(f"Updated subscription {subscription_id} status to {status}")


async def _handle_subscription_cancelled(conn, data: Dict[str, Any]):
    """Handle subscription.cancelled event."""
    subscription_id = data.get("id")
    cancellation_effective_date = data.get("cancellation_effective_date")
    
    if not subscription_id:
        return
    
    # Find user by subscription ID
    user = await conn.fetchrow(
        "SELECT user_id FROM users WHERE subscription_id = $1",
        str(subscription_id)
    )
    
    if not user:
        print(f"User not found for subscription_id: {subscription_id}")
        return
    
    # Mark for downgrade at period end
    from datetime import datetime
    ends_at = None
    if cancellation_effective_date:
        try:
            ends_at = datetime.fromisoformat(cancellation_effective_date.replace("Z", "+00:00"))
        except:
            pass
    
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid",  # Keep paid until period end
        subscription_status="cancelled",
        subscription_ends_at=ends_at,
    )
    
    print(f"Cancelled subscription {subscription_id}, effective: {ends_at}")


async def _handle_payment_succeeded(conn, data: Dict[str, Any]):
    """Handle payment.succeeded event."""
    subscription_id = data.get("subscription_id")
    
    if not subscription_id:
        return
    
    # Find user by subscription ID
    user = await conn.fetchrow(
        "SELECT user_id FROM users WHERE subscription_id = $1",
        str(subscription_id)
    )
    
    if not user:
        print(f"User not found for subscription_id: {subscription_id}")
        return
    
    # Extend subscription (Paddle handles this, but we update status)
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid",
        subscription_status="active",
    )
    
    print(f"Payment succeeded for subscription {subscription_id}")


async def _handle_payment_failed(conn, data: Dict[str, Any]):
    """Handle payment.failed event."""
    subscription_id = data.get("subscription_id")
    
    if not subscription_id:
        return
    
    # Find user by subscription ID
    user = await conn.fetchrow(
        "SELECT user_id FROM users WHERE subscription_id = $1",
        str(subscription_id)
    )
    
    if not user:
        print(f"User not found for subscription_id: {subscription_id}")
        return
    
    # Mark as past due
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid",  # Keep paid status
        subscription_status="past_due",
    )
    
    print(f"Payment failed for subscription {subscription_id}")


@router.get("/checkout-url")
async def get_checkout_url(
    user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get Paddle checkout URL for user.
    
    Returns checkout URL that user can redirect to.
    """
    settings = get_settings()
    
    if not settings.paddle_vendor_id or not settings.paddle_public_key:
        raise HTTPException(status_code=500, detail="Paddle not configured")
    
    # For now, return a simple checkout URL
    # In production, you'd generate a proper checkout link via Paddle API
    # This is a placeholder - you'll need to implement proper checkout link generation
    
    checkout_url = f"https://checkout.paddle.com/checkout/{settings.paddle_vendor_id}"
    
    return {
        "checkout_url": checkout_url,
        "message": "Redirect user to this URL to complete checkout",
    }
