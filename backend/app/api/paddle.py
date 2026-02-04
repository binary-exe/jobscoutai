"""
Paddle payment webhook handler for Apply Workspace.

Handles subscription events from Paddle.
Checkout requires authenticated Supabase user (no anonymous users for billing).
"""

import hmac
import hashlib
import json
from typing import Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Header, Depends
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
        except:
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


async def _handle_subscription_created(conn, data: Dict[str, Any]):
    """Handle subscription.created event."""
    customer_id = data.get("customer_id")
    subscription_id = data.get("id")
    
    if not subscription_id:
        print(f"Missing subscription_id in subscription.created: {data}")
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for subscription.created: customer_id={customer_id}, custom_data={data.get('custom_data')}")
        return
    
    # Upgrade to paid
    await apply_storage.update_user_plan(
        conn,
        user_id=user["user_id"],
        plan="paid",
        subscription_id=str(subscription_id),
        paddle_customer_id=str(customer_id) if customer_id else None,
        subscription_status="active",
    )
    
    print(f"Upgraded user {user['user_id']} to paid plan")


async def _handle_subscription_updated(conn, data: Dict[str, Any]):
    """Handle subscription.updated event."""
    subscription_id = data.get("id")
    status = data.get("status")
    
    if not subscription_id:
        return
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for subscription.updated: subscription_id={subscription_id}")
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
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for payment.succeeded: subscription_id={subscription_id}")
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
    
    # Find user using multiple strategies
    user = await _find_user_from_webhook(conn, data)
    
    if not user:
        print(f"User not found for payment.failed: subscription_id={subscription_id}")
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
    auth_user: AuthUser = Depends(get_current_user),
):
    """
    Get Paddle checkout URL for authenticated user.
    
    Creates a checkout link via Paddle API for the Pro subscription (€9/month).
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
        
        # Check if user already has a subscription
        if user.get("plan") == "paid" and user.get("subscription_status") == "active":
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
            
            # Get product ID from settings (or use vendor_id as fallback)
            # In Paddle, you need to create a product and get its ID
            product_id = settings.paddle_product_id or settings.paddle_vendor_id
            
            if not product_id:
                raise HTTPException(
                    status_code=500,
                    detail="Paddle product ID not configured. Set JOBSCOUT_PADDLE_PRODUCT_ID or JOBSCOUT_PADDLE_VENDOR_ID"
                )
            
            # Generate checkout link using Paddle's transaction preview API
            # This creates a checkout link for a subscription
            checkout_data = {
                "items": [
                    {
                        "price_id": product_id,  # This should be your subscription price_id from Paddle
                        "quantity": 1,
                    }
                ],
                "customer_id": paddle_customer_id,
                "custom_data": {
                    "user_id": str(user_uuid),
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
            # This requires product_id to be set up in Paddle dashboard
            base_url = "https://checkout.paddle.com" if settings.paddle_environment == "production" else "https://sandbox-checkout.paddle.com"
            
            # Build checkout URL with customer ID if available
            checkout_params = {
                "product": product_id,
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
