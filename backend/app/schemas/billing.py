from pydantic import BaseModel

from app.models.enums import SubscriptionTier


class CheckoutSessionRequest(BaseModel):
    tier: SubscriptionTier


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class BillingPortalOut(BaseModel):
    portal_url: str


class PlanOut(BaseModel):
    tier: SubscriptionTier
    price: float
    currency: str
    available: bool


class SubscriptionStatusOut(BaseModel):
    tier: SubscriptionTier
    # False for a free user, and also for a paid one whose subscription was
    # cancelled but whose paid period hasn't run out yet — in that state there
    # is nothing left to manage, so the UI must not offer to manage it.
    has_subscription: bool
    currency: str
    # Served rather than hardcoded in the UI: the real price lives on the
    # Paystack plan, and a figure duplicated in the React tree is a figure
    # that will eventually disagree with what the card is actually charged.
    plans: list[PlanOut]
