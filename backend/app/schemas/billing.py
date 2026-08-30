from pydantic import BaseModel

from app.models.enums import SubscriptionTier


class CheckoutSessionRequest(BaseModel):
    tier: SubscriptionTier


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class BillingPortalOut(BaseModel):
    portal_url: str
