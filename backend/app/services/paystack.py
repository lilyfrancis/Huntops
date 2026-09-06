"""Thin Paystack client over httpx.

Deliberately not the vendor SDK, matching how every other outbound integration
here (Gmail, Apollo, the job boards) talks to its API directly. Paystack's REST
surface is small enough that a wrapper buys nothing but a dependency.

Two Paystack-specific facts drive the shapes below:

  * Amounts are in the currency's *subunit* — kobo for NGN, cents for USD. A
    plan carries its own amount, so initializing against a plan code avoids
    ever having to do that conversion in application code.
  * Cancelling a subscription needs both its code and an `email_token` that
    Paystack only ever hands you once, on the `subscription.create` webhook.
    Lose it and the user cannot cancel without support intervention, which is
    why it is persisted on the user row rather than fetched on demand.
"""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

API_BASE = "https://api.paystack.co"
HTTP_TIMEOUT = 20.0


class PaystackError(Exception):
    pass


def _headers() -> dict:
    if not settings.PAYSTACK_SECRET_KEY:
        raise PaystackError("PAYSTACK_SECRET_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, **kwargs) -> dict:
    resp = httpx.request(method, f"{API_BASE}{path}", headers=_headers(), timeout=HTTP_TIMEOUT, **kwargs)

    try:
        body = resp.json()
    except ValueError:
        raise PaystackError(f"Paystack returned a non-JSON response ({resp.status_code}): {resp.text[:300]}")

    # Paystack answers 200 with {"status": false} for application-level
    # failures, so the HTTP code alone is not enough to tell success from
    # "your plan code doesn't exist".
    if resp.status_code >= 400 or not body.get("status"):
        raise PaystackError(f"Paystack {path} failed ({resp.status_code}): {body.get('message', resp.text[:300])}")

    return body.get("data") or {}


def create_customer(*, email: str, full_name: str) -> str:
    """Returns the customer code (`CUS_...`)."""
    first, _, last = full_name.partition(" ")
    data = _request("POST", "/customer", json={"email": email, "first_name": first, "last_name": last})
    return data["customer_code"]


def initialize_transaction(*, email: str, plan_code: str, callback_url: str, metadata: dict) -> str:
    """Start a subscription checkout. Returns the hosted payment page URL.

    The amount is deliberately omitted: passing a plan code makes Paystack
    charge the plan's own amount, so the price lives in one place (the Paystack
    dashboard) instead of being duplicated here where it could drift.
    """
    data = _request(
        "POST",
        "/transaction/initialize",
        json={"email": email, "plan": plan_code, "callback_url": callback_url, "metadata": metadata},
    )
    return data["authorization_url"]


def verify_transaction(reference: str) -> dict:
    return _request("GET", f"/transaction/verify/{reference}")


def manage_subscription_link(subscription_code: str) -> str:
    """Paystack's equivalent of a billing portal: a hosted page where the
    customer can update their card or cancel."""
    data = _request("GET", f"/subscription/{subscription_code}/manage/link")
    return data["link"]


def disable_subscription(*, subscription_code: str, email_token: str) -> None:
    _request("POST", "/subscription/disable", json={"code": subscription_code, "token": email_token})
