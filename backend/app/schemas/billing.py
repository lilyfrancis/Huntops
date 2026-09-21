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
    # Sent for the same reason the price is: the landing page had its own
    # copy of these and they went stale the moment the plans were resized.
    credits: int


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


class CreditCostsOut(BaseModel):
    """What one of each chargeable action costs.

    Served for the same reason the prices are. The pricing page shows what a
    month of credits buys, and that arithmetic has to use the numbers the
    charging code actually uses — a second copy in the UI would quietly start
    promising a count the product does not honour.
    """

    unlock: int
    tailor: int
    concierge: int


class CreditPackOut(BaseModel):
    code: str
    credits: int
    price: float
    currency: str


class CreditPackRequest(BaseModel):
    pack: str
