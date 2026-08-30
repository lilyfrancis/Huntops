import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.billing import BillingPortalOut, CheckoutSessionOut, CheckoutSessionRequest
from app.services import billing as billing_service

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CheckoutSessionOut(checkout_url=url)


@router.get("/portal", response_model=BillingPortalOut)
def billing_portal(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingPortalOut:
    url = billing_service.create_portal_session(db, current_user)
    return BillingPortalOut(portal_url=url)


@router.post("/webhook", status_code=200)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    billing_service.process_webhook_event(db, event)
    return {"received": True}
