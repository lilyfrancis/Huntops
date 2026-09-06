"""Subscription billing on Paystack.

The webhook is the only thing that grants a tier. A user returning from the
payment page proves nothing — the callback URL is just a redirect they could
type themselves — so the redirect only ever shows a "we're confirming" state,
and entitlement waits for a signed server-to-server event.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import SubscriptionTier
from app.models.user import User
from app.services import paystack
from app.services.credits import adjust_credits

logger = logging.getLogger(__name__)
settings = get_settings()


class PlanNotConfiguredError(Exception):
    pass


class NoSubscriptionError(Exception):
    pass


def tier_plan_codes() -> dict[SubscriptionTier, str]:
    """Read at call time, not import time, so tests can override settings."""
    return {
        SubscriptionTier.pro: settings.PAYSTACK_PLAN_PRO,
        SubscriptionTier.elite: settings.PAYSTACK_PLAN_ELITE,
    }


def tier_credits() -> dict[SubscriptionTier, int]:
    return {
        SubscriptionTier.free: settings.FREE_TIER_CREDITS,
        SubscriptionTier.pro: settings.PRO_TIER_CREDITS,
        SubscriptionTier.elite: settings.ELITE_TIER_CREDITS,
    }


def _tier_for_plan_code(plan_code: str | None) -> SubscriptionTier | None:
    if not plan_code:
        return None
    for tier, code in tier_plan_codes().items():
        if code and code == plan_code:
            return tier
    return None


def _get_or_create_customer(db: Session, user: User) -> str:
    if user.paystack_customer_code:
        return user.paystack_customer_code

    code = paystack.create_customer(email=user.email, full_name=user.full_name)
    user.paystack_customer_code = code
    db.commit()
    return code


def create_checkout_session(db: Session, user: User, tier: SubscriptionTier) -> str:
    plan_code = tier_plan_codes().get(tier)
    if not plan_code:
        raise PlanNotConfiguredError(f"No Paystack plan configured for tier '{tier.value}'")

    # Created up front so the customer exists before the first charge, which
    # keeps the customer_code on the webhook matched to a user we already know.
    _get_or_create_customer(db, user)

    return paystack.initialize_transaction(
        email=user.email,
        plan_code=plan_code,
        callback_url=f"{settings.FRONTEND_URL}/app/profile?billing=processing",
        metadata={"user_id": str(user.id), "tier": tier.value},
    )


def create_portal_session(db: Session, user: User) -> str:
    """Paystack's hosted manage-subscription page: update card, or cancel."""
    if not user.paystack_subscription_code:
        raise NoSubscriptionError("No active subscription to manage")
    return paystack.manage_subscription_link(user.paystack_subscription_code)


def cancel_subscription(db: Session, user: User) -> None:
    if not (user.paystack_subscription_code and user.paystack_email_token):
        raise NoSubscriptionError("No active subscription to cancel")
    paystack.disable_subscription(
        subscription_code=user.paystack_subscription_code, email_token=user.paystack_email_token
    )
    # The tier is not downgraded here. Paystack keeps a cancelled subscription
    # live until the period it was paid for ends, and the subscription.disable
    # webhook fires then — downgrading now would take away time already paid for.


def _set_tier(db: Session, user: User, tier: SubscriptionTier, credit_action: str) -> None:
    user.subscription_tier = tier
    adjust_credits(db, user, action=credit_action, amount=tier_credits()[tier])
    db.commit()


def _user_from_event(db: Session, data: dict) -> User | None:
    """Find the user an event belongs to.

    Tried in order of reliability: our own metadata (only present on events
    originating from a checkout we started), then the Paystack customer code,
    then the email. Email last because it is the one a customer can change in
    Paystack without us hearing about it.
    """
    user_id = (data.get("metadata") or {}).get("user_id")
    if user_id:
        try:
            user = db.get(User, uuid.UUID(user_id))
        except (ValueError, TypeError):
            user = None
        if user:
            return user

    customer = data.get("customer") or {}
    code = customer.get("customer_code")
    if code:
        user = db.query(User).filter(User.paystack_customer_code == code).first()
        if user:
            return user

    email = customer.get("email")
    if email:
        return db.query(User).filter(User.email == email).first()

    return None


def handle_subscription_create(db: Session, data: dict) -> None:
    """The event that grants a tier — and the only place the email token
    Paystack needs for cancellation is ever visible."""
    user = _user_from_event(db, data)
    if user is None:
        logger.warning("subscription.create for an unknown customer: %s", (data.get("customer") or {}).get("email"))
        return

    plan_code = (data.get("plan") or {}).get("plan_code")
    tier = _tier_for_plan_code(plan_code)
    if tier is None:
        logger.warning("subscription.create for unrecognised plan_code=%s — tier unchanged", plan_code)
        return

    user.paystack_subscription_code = data.get("subscription_code")
    user.paystack_email_token = data.get("email_token")
    if not user.paystack_customer_code:
        user.paystack_customer_code = (data.get("customer") or {}).get("customer_code")

    _set_tier(db, user, tier, credit_action=f"paystack_subscription:{tier.value}")


def handle_charge_success(db: Session, data: dict) -> None:
    """A successful renewal charge: top the credits back up for the period.

    The first charge of a new subscription arrives here too, alongside
    subscription.create. Granting twice for one payment would be a real bug, so
    this only refills a user already on the plan the charge is for — the
    initial grant belongs to subscription.create, which is the event that knows
    the subscription code and email token.
    """
    user = _user_from_event(db, data)
    if user is None:
        return

    plan = data.get("plan")
    # A one-off charge (no plan) is not a subscription renewal.
    if not isinstance(plan, dict):
        return

    tier = _tier_for_plan_code(plan.get("plan_code"))
    if tier is None or user.subscription_tier != tier:
        return

    _set_tier(db, user, tier, credit_action=f"paystack_renewal:{tier.value}")


def handle_subscription_disable(db: Session, data: dict) -> None:
    user = _user_from_event(db, data)
    if user is None:
        return

    # Guard against a stale event for a subscription the user has already
    # replaced with a new one — downgrading then would cancel a live upgrade.
    code = data.get("subscription_code")
    if code and user.paystack_subscription_code and code != user.paystack_subscription_code:
        logger.info("Ignoring subscription.disable for superseded subscription %s", code)
        return

    user.paystack_subscription_code = None
    user.paystack_email_token = None
    _set_tier(db, user, SubscriptionTier.free, credit_action="paystack_cancelled")


def handle_invoice_payment_failed(db: Session, data: dict) -> None:
    """Logged, not acted on. Paystack retries a failed renewal for days before
    giving up and disabling the subscription, and that disable event is what
    should downgrade — cutting access on the first failed retry would punish
    someone whose card simply needed a second attempt."""
    user = _user_from_event(db, data)
    if user:
        logger.warning("Paystack renewal failed for user=%s — awaiting retries", user.id)


_HANDLERS = {
    "subscription.create": handle_subscription_create,
    "charge.success": handle_charge_success,
    "subscription.disable": handle_subscription_disable,
    "subscription.not_renew": handle_invoice_payment_failed,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


def process_webhook_event(db: Session, event: dict) -> None:
    handler = _HANDLERS.get(event.get("event", ""))
    if handler:
        handler(db, event.get("data") or {})
    else:
        logger.info("Unhandled Paystack event: %s", event.get("event"))
