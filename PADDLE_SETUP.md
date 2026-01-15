# Paddle Payment Integration Guide

## Overview

Paddle is used as the payment processor for JobScoutAI Apply Workspace. Paddle acts as the Merchant of Record (MoR), handling taxes and compliance.

## Why Paddle?

- **No business verification required** for individuals/sole traders
- **Merchant of Record** - handles taxes automatically
- **Simple integration** - hosted checkout + webhooks
- **Supports subscriptions** - perfect for monthly plans

## Setup Steps

### 1. Create Paddle Account

1. Go to https://vendors.paddle.com/signup
2. Sign up as an individual/sole trader
3. Complete identity verification (required)
4. Note: Business verification is NOT required for individuals

### 2. Get API Credentials

1. Go to **Developer Tools > Authentication**
2. Copy:
   - **Vendor ID** (found in URL: `https://vendors.paddle.com/vendor/{vendor_id}`)
   - **API Key** (create one if needed)
   - **Public Key** (for client-side validation)

### 3. Create Products

1. Go to **Catalog > Products**
2. Create product: **JobScoutAI Pro**
   - Type: Subscription
   - Price: €9/month
   - Billing cycle: Monthly
   - Product ID: Note this for webhook handling

### 4. Set Up Webhooks

1. Go to **Developer Tools > Notifications**
2. Add webhook URL: `https://jobscout-api.fly.dev/api/v1/paddle/webhook`
3. Select events:
   - `subscription.created`
   - `subscription.updated`
   - `subscription.cancelled`
   - `payment.succeeded`
   - `payment.failed`
4. Copy **Webhook Secret** (for signature verification)

### 5. Configure Environment Variables

Add to Fly.io secrets:

```bash
fly secrets set JOBSCOUT_PADDLE_VENDOR_ID="your_vendor_id" -a jobscout-api
fly secrets set JOBSCOUT_PADDLE_API_KEY="your_api_key" -a jobscout-api
fly secrets set JOBSCOUT_PADDLE_PUBLIC_KEY="your_public_key" -a jobscout-api
fly secrets set JOBSCOUT_PADDLE_WEBHOOK_SECRET="your_webhook_secret" -a jobscout-api
fly secrets set JOBSCOUT_PADDLE_ENVIRONMENT="sandbox" -a jobscout-api
```

For production, change `PADDLE_ENVIRONMENT` to `production`.

## Implementation

### Backend Webhook Handler

Create `backend/app/api/paddle.py`:

```python
from fastapi import APIRouter, HTTPException, Header, Request
import hmac
import hashlib

router = APIRouter(prefix="/paddle", tags=["paddle"])

@router.post("/webhook")
async def handle_webhook(
    request: Request,
    p_signature: str = Header(..., alias="p-signature"),
):
    """Handle Paddle webhook events."""
    body = await request.body()
    
    # Verify signature
    settings = get_settings()
    signature = hmac.new(
        settings.paddle_webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if signature != p_signature:
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    event = await request.json()
    event_type = event.get("event_type")
    
    # Handle events
    if event_type == "subscription.created":
        # Upgrade user to paid
        await upgrade_user_to_paid(event)
    elif event_type == "subscription.updated":
        # Update subscription status
        await update_subscription(event)
    elif event_type == "subscription.cancelled":
        # Mark for downgrade at period end
        await mark_for_downgrade(event)
    elif event_type == "payment.succeeded":
        # Extend subscription
        await extend_subscription(event)
    elif event_type == "payment.failed":
        # Handle failed payment
        await handle_failed_payment(event)
    
    return {"status": "ok"}
```

### Frontend Checkout

Use Paddle's hosted checkout:

```typescript
// frontend/lib/paddle.ts
declare global {
  interface Window {
    Paddle: any;
  }
}

export function initPaddle(publicKey: string) {
  if (typeof window !== 'undefined' && !window.Paddle) {
    const script = document.createElement('script');
    script.src = 'https://cdn.paddle.com/paddle/paddle.js';
    script.onload = () => {
      window.Paddle.Setup({ vendor: parseInt(publicKey) });
    };
    document.body.appendChild(script);
  }
}

export function openCheckout(productId: number, userId: string) {
  window.Paddle.Checkout.open({
    product: productId,
    email: userId, // Or user email if available
    passthrough: JSON.stringify({ user_id: userId }),
    successCallback: (data: any) => {
      // Redirect to success page
      window.location.href = '/account?upgraded=true';
    },
  });
}
```

### Subscription Management

Paddle provides a hosted customer portal. Link to it:

```typescript
export function getCustomerPortalUrl(customerId: string): string {
  return `https://vendors.paddle.com/customers/${customerId}/portal`;
}
```

## Testing

### Sandbox Mode

1. Use Paddle sandbox credentials
2. Test with sandbox card: `4242 4242 4242 4242`
3. Use any future expiry date and any CVC

### Webhook Testing

Use Paddle's webhook testing tool or ngrok:

```bash
ngrok http 8000
# Use ngrok URL in Paddle webhook settings
```

## Event Handling

### subscription.created
- Set `users.plan = 'paid'`
- Set `users.subscription_id = event.subscription_id`
- Set `users.paddle_customer_id = event.customer_id`
- Set `users.subscription_status = 'active'`

### subscription.cancelled
- Set `users.subscription_status = 'cancelled'`
- Set `users.subscription_ends_at = event.cancellation_effective_date`
- User keeps access until period end

### payment.succeeded
- Extend `users.subscription_ends_at` by 1 month
- Set `users.subscription_status = 'active'`

### payment.failed
- Set `users.subscription_status = 'past_due'`
- Send notification (optional)

## Security

- Always verify webhook signatures
- Never trust client-side data
- Use HTTPS for webhook endpoints
- Store sensitive data (subscription IDs) securely

## Resources

- [Paddle API Docs](https://developer.paddle.com/)
- [Paddle Webhooks](https://developer.paddle.com/webhook-reference/overview)
- [Paddle Checkout](https://developer.paddle.com/guides/how-tos/checkout/implement-checkout)
