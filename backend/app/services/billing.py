import logging
import uuid

import stripe
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import SubscriptionTier
from app.models.user import User
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

TIER_PRICE_IDS: dict[SubscriptionTier, str] = {
    SubscriptionTier.pro: settings.STRIPE_PRICE_PRO,
    SubscriptionTier.elite: settings.STRIPE_PRICE_ELITE,
}

TIER_CREDITS: dict[SubscriptionTier, int] = {
    SubscriptionTier.free: settings.FREE_TIER_CREDITS,
    SubscriptionTier.pro: settings.PRO_TIER_CREDITS,
    SubscriptionTier.elite: settings.ELITE_TIER_CREDITS,
}

PRICE_ID_TO_TIER: dict[str, SubscriptionTier] = {
    price_id: tier for tier, price_id in TIER_PRICE_IDS.items() if price_id
}


def _get_or_create_stripe_customer(db: Session, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(email=user.email, name=user.full_name, metadata={"user_id": str(user.id)})
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def create_checkout_session(db: Session, user: User, tier: SubscriptionTier) -> str:
    price_id = TIER_PRICE_IDS.get(tier)
    if not price_id:
        raise ValueError(f"No Stripe price configured for tier '{tier.value}'")

    customer_id = _get_or_create_stripe_customer(db, user)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.FRONTEND_URL}/billing/cancelled",
        metadata={"user_id": str(user.id), "tier": tier.value},
    )
    return session.url


def create_portal_session(db: Session, user: User) -> str:
    customer_id = _get_or_create_stripe_customer(db, user)
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.FRONTEND_URL}/billing",
    )
    return session.url


def _set_tier(db: Session, user: User, tier: SubscriptionTier, credit_action: str) -> None:
    user.subscription_tier = tier
    adjust_credits(db, user, action=credit_action, amount=TIER_CREDITS[tier])
    db.commit()


def handle_checkout_completed(db: Session, event_data: dict) -> None:
    user_id = event_data.get("metadata", {}).get("user_id")
    subscription_id = event_data.get("subscription")
    if not user_id:
        logger.warning("checkout.session.completed with no user_id in metadata")
        return

    try:
        user = db.get(User, uuid.UUID(user_id))
    except (ValueError, TypeError):
        user = None
    if not user:
        logger.warning("checkout.session.completed for unknown user_id=%s", user_id)
        return

    tier = SubscriptionTier(event_data.get("metadata", {}).get("tier", SubscriptionTier.pro.value))
    user.stripe_subscription_id = subscription_id
    _set_tier(db, user, tier, credit_action=f"stripe_checkout:{tier.value}")


def handle_subscription_updated(db: Session, event_data: dict) -> None:
    customer_id = event_data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    items = event_data.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    tier = PRICE_ID_TO_TIER.get(price_id)
    if tier and event_data.get("status") in ("active", "trialing"):
        _set_tier(db, user, tier, credit_action=f"stripe_renewal:{tier.value}")


def handle_subscription_deleted(db: Session, event_data: dict) -> None:
    customer_id = event_data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.stripe_subscription_id = None
    _set_tier(db, user, SubscriptionTier.free, credit_action="stripe_cancelled")


def process_webhook_event(db: Session, event: stripe.Event) -> None:
    handlers = {
        "checkout.session.completed": handle_checkout_completed,
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
    }
    handler = handlers.get(event["type"])
    if handler:
        handler(db, event["data"]["object"])
    else:
        logger.info("Unhandled Stripe event type: %s", event["type"])
