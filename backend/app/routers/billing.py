import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.enums import SubscriptionTier
from app.schemas.billing import (
    BillingPortalOut,
    CheckoutSessionOut,
    CheckoutSessionRequest,
    PlanOut,
    SubscriptionStatusOut,
)
from app.services import billing as billing_service
from app.services.paystack import PaystackError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])
settings = get_settings()


@router.post("/checkout-session", response_model=CheckoutSessionOut)
def create_checkout_session(
    payload: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutSessionOut:
    try:
        url = billing_service.create_checkout_session(db, current_user, payload.tier)
    except billing_service.PlanNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaystackError as e:
        logger.error("Paystack checkout failed for user=%s: %s", current_user.id, e)
        raise HTTPException(status_code=502, detail="Payment provider is unavailable — please try again shortly")
    return CheckoutSessionOut(checkout_url=url)


@router.get("/status", response_model=SubscriptionStatusOut)
def subscription_status(current_user: User = Depends(get_current_user)) -> SubscriptionStatusOut:
    plan_codes = billing_service.tier_plan_codes()
    prices = {SubscriptionTier.pro: settings.PRO_PRICE, SubscriptionTier.elite: settings.ELITE_PRICE}
    return SubscriptionStatusOut(
        tier=current_user.subscription_tier,
        has_subscription=bool(current_user.paystack_subscription_code),
        currency=settings.BILLING_CURRENCY,
        plans=[
            PlanOut(
                tier=tier,
                price=price,
                currency=settings.BILLING_CURRENCY,
                # A tier with no plan code cannot be bought, so the UI must not
                # offer a button that would only ever return a 400.
                available=bool(plan_codes.get(tier)),
            )
            for tier, price in prices.items()
        ],
    )


@router.get("/portal", response_model=BillingPortalOut)
def billing_portal(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingPortalOut:
    try:
        url = billing_service.create_portal_session(db, current_user)
    except billing_service.NoSubscriptionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PaystackError as e:
        logger.error("Paystack manage link failed for user=%s: %s", current_user.id, e)
        raise HTTPException(status_code=502, detail="Payment provider is unavailable — please try again shortly")
    return BillingPortalOut(portal_url=url)


@router.post("/cancel", status_code=204)
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        billing_service.cancel_subscription(db, current_user)
    except billing_service.NoSubscriptionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PaystackError as e:
        logger.error("Paystack cancel failed for user=%s: %s", current_user.id, e)
        raise HTTPException(status_code=502, detail="Payment provider is unavailable — please try again shortly")


@router.post("/webhook", status_code=200)
async def paystack_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """The only thing that can change a user's tier.

    Paystack signs the raw body with HMAC-SHA512 using the *secret key* — the
    same key used to call the API, not a separate webhook secret. Verification
    must run against the exact bytes received: re-serializing the parsed JSON
    would reorder keys and change the digest.
    """
    raw = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if not settings.PAYSTACK_SECRET_KEY:
        # Without the key nothing can be verified, so nothing may be trusted.
        # Refusing loudly beats silently granting tiers to anyone who can POST.
        logger.error("Paystack webhook received but PAYSTACK_SECRET_KEY is unset — rejecting")
        raise HTTPException(status_code=503, detail="Billing is not configured")

    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw, hashlib.sha512).hexdigest()
    # compare_digest, not ==: a short-circuiting comparison leaks how much of a
    # forged signature was correct, one byte at a time.
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    billing_service.process_webhook_event(db, event)
    return {"received": True}
