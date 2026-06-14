"""
Subscription & Payment Routes - Stripe Integration

Handles subscription management, upgrades/downgrades, and payment processing.
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import os

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
import stripe

from api.auth_routes import get_current_user, get_optional_user
from shared.database import get_postgres
from shared.logger import setup_logging

logger = setup_logging("subscription-api")
router = APIRouter(prefix="/api/subscription", tags=["Subscription"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Price IDs (set these in .env)
# Tier ladder: freemium ($0) → basic ($10) → pro ($20) → enterprise (custom)
# "basic" and "standard" are aliases; the canonical slug for the $10 tier is "basic".
PRICE_IDS = {
    "basic": os.getenv("STRIPE_PRICE_ID_BASIC", os.getenv("STRIPE_PRICE_ID_STANDARD", "")),
    "standard": os.getenv("STRIPE_PRICE_ID_BASIC", os.getenv("STRIPE_PRICE_ID_STANDARD", "")),
    "pro": os.getenv("STRIPE_PRICE_ID_PRO", os.getenv("STRIPE_PRICE_ID_PROFESSIONAL", "")),
    "professional": os.getenv("STRIPE_PRICE_ID_PRO", os.getenv("STRIPE_PRICE_ID_PROFESSIONAL", "")),
    "enterprise": os.getenv("STRIPE_PRICE_ID_ENTERPRISE", ""),
}

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SubscriptionInfo(BaseModel):
    """Current subscription information"""
    tier: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class CreateSubscriptionRequest(BaseModel):
    """Request to create a new subscription"""
    tier: str = Field(..., pattern="^(basic|standard|pro|professional|enterprise)$")
    payment_method_id: str = Field(..., description="Stripe payment method ID")


class UpgradeSubscriptionRequest(BaseModel):
    """Request to upgrade/downgrade subscription"""
    new_tier: str = Field(..., pattern="^(basic|standard|pro|professional|enterprise)$")


class PaymentHistoryItem(BaseModel):
    """Payment history record"""
    id: str
    amount: float
    currency: str
    status: str
    description: str
    created_at: datetime
    invoice_url: Optional[str] = None


# =============================================================================
# SUBSCRIPTION MANAGEMENT
# =============================================================================

@router.get("/current", response_model=SubscriptionInfo)
async def get_current_subscription(
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """
    Get current subscription information.

    Returns details about the user's active subscription including
    billing period, status, and Stripe identifiers.
    Returns a freemium default when no user is authenticated, no
    subscription row exists, or the subscriptions table has not been created yet.
    """
    freemium_default = SubscriptionInfo(
        tier="freemium",
        status="active",
        cancel_at_period_end=False,
    )

    if not current_user:
        return freemium_default

    freemium_default.tier = current_user.get("subscription_tier", "freemium") or "freemium"
    freemium_default.stripe_customer_id = current_user.get("stripe_customer_id")

    try:
        db = get_postgres()

        result = db.execute_query(
            """
            SELECT
                tier,
                status,
                stripe_customer_id,
                stripe_subscription_id,
                current_period_start,
                current_period_end,
                cancel_at_period_end
            FROM subscriptions
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
            """,
            params={"user_id": current_user["user_id"]}
        )

        if not result:
            return freemium_default

        row = result[0]
        return SubscriptionInfo(
            tier=row.get("tier") or "freemium",
            status=row.get("status") or "active",
            current_period_start=row.get("current_period_start"),
            current_period_end=row.get("current_period_end"),
            cancel_at_period_end=row.get("cancel_at_period_end", False),
            stripe_customer_id=row.get("stripe_customer_id"),
            stripe_subscription_id=row.get("stripe_subscription_id")
        )

    except Exception as e:
        logger.warning(f"Failed to query subscription for user {current_user.get('user_id')}: {e}")
        return freemium_default


@router.post("/create")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new subscription.

    Steps:
    1. Create Stripe customer (if not exists)
    2. Attach payment method
    3. Create subscription
    4. Update database

    **Frontend should:**
    - Collect payment details using Stripe.js
    - Create payment method
    - Send payment_method_id to this endpoint
    """
    db = get_postgres()

    try:
        # Check if user already has subscription
        existing = db.execute_query(
            "SELECT subscription_id FROM subscriptions WHERE user_id = :user_id AND status = 'active'",
            params={"user_id": current_user["user_id"]}
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="User already has an active subscription. Use upgrade endpoint instead."
            )

        # Get or create Stripe customer
        stripe_customer_id = current_user.get("stripe_customer_id")

        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user["email"],
                name=current_user.get("full_name", ""),
                metadata={"user_id": current_user["user_id"]}
            )
            stripe_customer_id = customer.id

            # Update user record
            db.execute_update(
                "UPDATE users SET stripe_customer_id = :stripe_id WHERE user_id = :user_id",
                params={"stripe_id": stripe_customer_id, "user_id": current_user["user_id"]}
            )

        # Attach payment method
        stripe.PaymentMethod.attach(
            request.payment_method_id,
            customer=stripe_customer_id
        )

        # Set as default payment method
        stripe.Customer.modify(
            stripe_customer_id,
            invoice_settings={
                "default_payment_method": request.payment_method_id
            }
        )

        # Create subscription
        price_id = PRICE_IDS.get(request.tier)
        if not price_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier or price ID not configured: {request.tier}"
            )

        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"],
            metadata={
                "user_id": current_user["user_id"],
                "tier": request.tier
            }
        )

        # Store in database
        subscription_id = str(uuid4())
        db.execute_update(
            """
            INSERT INTO subscriptions (
                subscription_id, user_id, tier, status,
                stripe_customer_id, stripe_subscription_id,
                stripe_price_id, current_period_start,
                current_period_end, created_at, updated_at
            ) VALUES (
                :id, :user_id, :tier, :status,
                :stripe_customer_id, :stripe_subscription_id,
                :stripe_price_id, :start_date,
                :end_date, NOW(), NOW()
            )
            """,
            params={
                "id": subscription_id,
                "user_id": current_user["user_id"],
                "tier": request.tier,
                "status": subscription.status,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": subscription.id,
                "stripe_price_id": price_id,
                "start_date": datetime.fromtimestamp(subscription.current_period_start),
                "end_date": datetime.fromtimestamp(subscription.current_period_end),
            }
        )

        # Update user tier
        db.execute_update(
            "UPDATE users SET subscription_tier = :tier WHERE user_id = :user_id",
            params={"tier": request.tier, "user_id": current_user["user_id"]}
        )

        logger.info(f"Subscription created: {subscription.id} for user {current_user['user_id']}")

        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret if subscription.latest_invoice else None
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.put("/upgrade")
async def upgrade_subscription(
    request: UpgradeSubscriptionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Upgrade or downgrade subscription tier.

    **Billing:**
    - Upgrades: Prorated immediately
    - Downgrades: Take effect at period end
    """
    db = get_postgres()

    try:
        # Get current subscription
        current = db.execute_query(
            """
            SELECT subscription_id, stripe_subscription_id, tier
            FROM subscriptions
            WHERE user_id = :user_id AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            params={"user_id": current_user["user_id"]}
        )

        if not current:
            raise HTTPException(
                status_code=400,
                detail="No active subscription found. Create a subscription first."
            )

        row = current[0]

        if row["tier"] == request.new_tier:
            raise HTTPException(
                status_code=400,
                detail="Already subscribed to this tier"
            )

        # Get new price ID
        new_price_id = PRICE_IDS.get(request.new_tier)
        if not new_price_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tier or price ID not configured: {request.new_tier}"
            )

        # Update Stripe subscription
        subscription = stripe.Subscription.retrieve(row["stripe_subscription_id"])

        updated_subscription = stripe.Subscription.modify(
            subscription.id,
            items=[{
                "id": subscription["items"]["data"][0].id,
                "price": new_price_id
            }],
            proration_behavior="always_invoice",
            metadata={
                "user_id": current_user["user_id"],
                "tier": request.new_tier
            }
        )

        # Update database
        db.execute_update(
            """
            UPDATE subscriptions
            SET tier = :tier,
                stripe_price_id = :price_id,
                updated_at = NOW()
            WHERE subscription_id = :id
            """,
            params={"tier": request.new_tier, "price_id": new_price_id, "id": row["subscription_id"]}
        )

        # Update user tier
        db.execute_update(
            "UPDATE users SET subscription_tier = :tier WHERE user_id = :user_id",
            params={"tier": request.new_tier, "user_id": current_user["user_id"]}
        )

        logger.info(
            f"Subscription upgraded: {row['tier']} -> {request.new_tier} "
            f"for user {current_user['user_id']}"
        )

        return {
            "message": "Subscription updated successfully",
            "new_tier": request.new_tier,
            "status": updated_subscription.status
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error upgrading subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to upgrade subscription")


@router.delete("/cancel")
async def cancel_subscription(
    immediate: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel subscription.

    **Parameters:**
    - immediate: If true, cancel immediately. If false, cancel at period end.
    """
    db = get_postgres()

    try:
        # Get current subscription
        current = db.execute_query(
            """
            SELECT subscription_id, stripe_subscription_id, current_period_end
            FROM subscriptions
            WHERE user_id = :user_id AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            params={"user_id": current_user["user_id"]}
        )

        if not current:
            raise HTTPException(
                status_code=400,
                detail="No active subscription found"
            )

        row = current[0]

        # Cancel in Stripe
        if immediate:
            stripe.Subscription.delete(row["stripe_subscription_id"])
            new_status = "canceled"
        else:
            stripe.Subscription.modify(
                row["stripe_subscription_id"],
                cancel_at_period_end=True
            )
            new_status = "active"

        # Update database
        db.execute_update(
            """
            UPDATE subscriptions
            SET status = :status,
                cancel_at_period_end = :cancel_at_end,
                cancelled_at = :cancelled_at,
                updated_at = NOW()
            WHERE subscription_id = :id
            """,
            params={
                "status": new_status,
                "cancel_at_end": not immediate,
                "cancelled_at": datetime.utcnow() if immediate else None,
                "id": row["subscription_id"],
            }
        )

        # If immediate, revert to freemium
        if immediate:
            db.execute_update(
                "UPDATE users SET subscription_tier = 'freemium' WHERE user_id = :user_id",
                params={"user_id": current_user["user_id"]}
            )

        logger.info(
            f"Subscription canceled ({'immediate' if immediate else 'at period end'}) "
            f"for user {current_user['user_id']}"
        )

        return {
            "message": "Subscription canceled successfully",
            "immediate": immediate,
            "access_until": row.get("current_period_end") if not immediate else None
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


# =============================================================================
# PAYMENT HISTORY
# =============================================================================

@router.get("/history", response_model=List[PaymentHistoryItem])
async def get_payment_history(
    limit: int = 20,
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """
    Get payment history for the user.

    Returns list of past invoices and payments.
    Returns an empty list if no user is authenticated, no payment
    history exists, or the payment_history table has not been created yet.
    """
    if not current_user:
        return []

    try:
        db = get_postgres()

        results = db.execute_query(
            """
            SELECT
                payment_id, amount_cents, currency, status,
                description, invoice_url, created_at
            FROM payment_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :lim
            """,
            params={"user_id": current_user["user_id"], "lim": limit}
        )

        return [
            PaymentHistoryItem(
                id=str(row["payment_id"]),
                amount=float(row.get("amount_cents", 0)) / 100,  # Convert cents to dollars
                currency=row.get("currency", "usd"),
                status=row.get("status", "unknown"),
                description=row.get("description", ""),
                invoice_url=row.get("invoice_url"),
                created_at=row["created_at"]
            )
            for row in (results or [])
        ]

    except Exception as e:
        logger.warning(f"Failed to query payment history for user {current_user.get('user_id')}: {e}")
        return []


# =============================================================================
# STRIPE WEBHOOKS
# =============================================================================

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature")
):
    """
    Handle Stripe webhook events.

    **Events handled:**
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = get_postgres()

    # Handle the event
    if event.type == "customer.subscription.created":
        subscription = event.data.object
        logger.info(f"Subscription created webhook: {subscription.id}")

    elif event.type == "customer.subscription.updated":
        subscription = event.data.object

        # Update subscription status
        db.execute_update(
            """
            UPDATE subscriptions
            SET status = :status,
                current_period_end = :end_date,
                updated_at = NOW()
            WHERE stripe_subscription_id = :stripe_id
            """,
            params={
                "status": subscription.status,
                "end_date": datetime.fromtimestamp(subscription.current_period_end),
                "stripe_id": subscription.id,
            }
        )

        logger.info(f"Subscription updated webhook: {subscription.id}")

    elif event.type == "customer.subscription.deleted":
        subscription = event.data.object

        # Mark as canceled
        db.execute_update(
            """
            UPDATE subscriptions
            SET status = 'canceled',
                updated_at = NOW()
            WHERE stripe_subscription_id = :stripe_id
            """,
            params={"stripe_id": subscription.id}
        )

        # Revert user to freemium
        user_id = subscription.metadata.get("user_id")
        if user_id:
            db.execute_update(
                "UPDATE users SET subscription_tier = 'freemium' WHERE user_id = :user_id",
                params={"user_id": user_id}
            )

        logger.info(f"Subscription deleted webhook: {subscription.id}")

    elif event.type == "invoice.payment_succeeded":
        invoice = event.data.object

        # Record payment
        customer_id = invoice.customer
        user_rows = db.execute_query(
            "SELECT user_id FROM users WHERE stripe_customer_id = :customer_id",
            params={"customer_id": customer_id}
        )

        if user_rows:
            db.execute_update(
                """
                INSERT INTO payment_history (
                    payment_id, user_id, stripe_invoice_id, amount_cents, currency,
                    status, description, invoice_url, created_at
                ) VALUES (
                    :id, :user_id, :invoice_id, :amount, :currency,
                    :status, :description, :invoice_url, NOW()
                )
                """,
                params={
                    "id": str(uuid4()),
                    "user_id": user_rows[0]["user_id"],
                    "invoice_id": invoice.id,
                    "amount": invoice.amount_paid,
                    "currency": invoice.currency,
                    "status": "succeeded",
                    "description": invoice.description or "Subscription payment",
                    "invoice_url": invoice.hosted_invoice_url,
                }
            )

        logger.info(f"Payment succeeded webhook: {invoice.id}")

    elif event.type == "invoice.payment_failed":
        invoice = event.data.object

        # Record failed payment
        customer_id = invoice.customer
        user_rows = db.execute_query(
            "SELECT user_id FROM users WHERE stripe_customer_id = :customer_id",
            params={"customer_id": customer_id}
        )

        if user_rows:
            db.execute_update(
                """
                INSERT INTO payment_history (
                    payment_id, user_id, stripe_invoice_id, amount_cents, currency,
                    status, description, created_at
                ) VALUES (
                    :id, :user_id, :invoice_id, :amount, :currency,
                    :status, :description, NOW()
                )
                """,
                params={
                    "id": str(uuid4()),
                    "user_id": user_rows[0]["user_id"],
                    "invoice_id": invoice.id,
                    "amount": invoice.amount_due,
                    "currency": invoice.currency,
                    "status": "failed",
                    "description": "Payment failed",
                }
            )

        logger.warning(f"Payment failed webhook: {invoice.id}")

    return {"status": "success"}
