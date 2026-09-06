"""Paystack billing. The webhook is the only thing that grants a tier, so
most of what matters is here rather than in the checkout path."""

import hashlib
import hmac
import json
import uuid
from unittest.mock import patch

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.enums import SubscriptionTier
from app.models.user import User
from app.services import billing as billing_service
from app.services.paystack import PaystackError
from tests.conftest import auth_headers, register_user

settings = get_settings()


def _subscription_event(user_id, *, plan_code=None, code="SUB_abc", token="tok_abc", email="billing@example.com"):
    return {
        "event": "subscription.create",
        "data": {
            "subscription_code": code,
            "email_token": token,
            "status": "active",
            "plan": {"plan_code": plan_code or settings.PAYSTACK_PLAN_PRO, "name": "Pro"},
            "customer": {"customer_code": "CUS_abc", "email": email},
            "metadata": {"user_id": str(user_id)},
        },
    }


def _signed(client, event: dict):
    raw = json.dumps(event).encode()
    signature = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw, hashlib.sha512).hexdigest()
    return client.post(
        "/api/billing/webhook",
        content=raw,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )


def _reload(user_id) -> User:
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        session.refresh(user)
        session.expunge(user)
        return user
    finally:
        session.close()


# ---------- signature verification ----------

def test_webhook_rejects_an_unsigned_request(client):
    """Without this check, anyone who can reach the URL can grant themselves
    the top tier by POSTing a JSON object."""
    resp = client.post("/api/billing/webhook", json={"event": "subscription.create", "data": {}})
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


def test_webhook_rejects_a_forged_signature(client):
    resp = client.post(
        "/api/billing/webhook",
        json={"event": "subscription.create", "data": {}},
        headers={"x-paystack-signature": "0" * 128},
    )
    assert resp.status_code == 400


def test_webhook_rejects_a_body_altered_after_signing(client):
    """The signature covers the exact bytes, so swapping the plan for a more
    expensive one after signing must not verify."""
    data = register_user(client, email="tamper@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    event = _subscription_event(user_id)
    raw = json.dumps(event).encode()
    signature = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw, hashlib.sha512).hexdigest()

    tampered = json.dumps(_subscription_event(user_id, plan_code=settings.PAYSTACK_PLAN_ELITE)).encode()
    resp = client.post(
        "/api/billing/webhook",
        content=tampered,
        headers={"x-paystack-signature": signature, "content-type": "application/json"},
    )
    assert resp.status_code == 400
    assert _reload(user_id).subscription_tier == SubscriptionTier.free


def test_a_correctly_signed_webhook_is_accepted(client):
    data = register_user(client, email="billing@example.com")
    resp = _signed(client, _subscription_event(uuid.UUID(data["user"]["id"])))
    assert resp.status_code == 200
    assert resp.json() == {"received": True}


# ---------- granting and revoking ----------

def test_subscription_create_upgrades_and_grants_credits(client):
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    assert _reload(user_id).ai_credits == 10  # signup bonus only

    _signed(client, _subscription_event(user_id))

    user = _reload(user_id)
    assert user.subscription_tier == SubscriptionTier.pro
    assert user.paystack_subscription_code == "SUB_abc"
    assert user.ai_credits == 10 + 100


def test_subscription_create_stores_the_email_token(client):
    """Paystack hands this out exactly once and cancellation needs it. Drop it
    and the user cannot cancel without someone opening the Paystack dashboard."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    _signed(client, _subscription_event(user_id, token="tok_xyz"))

    assert _reload(user_id).paystack_email_token == "tok_xyz"


def test_an_unrecognised_plan_code_changes_nothing(client):
    """A plan created in the dashboard but never wired into config must not
    silently map to a tier."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    _signed(client, _subscription_event(user_id, plan_code="PLN_never_configured"))

    user = _reload(user_id)
    assert user.subscription_tier == SubscriptionTier.free
    assert user.ai_credits == 10


def test_subscription_disable_downgrades_to_free(client):
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id))

    _signed(client, {
        "event": "subscription.disable",
        "data": {
            "subscription_code": "SUB_abc",
            "customer": {"customer_code": "CUS_abc", "email": "billing@example.com"},
        },
    })

    user = _reload(user_id)
    assert user.subscription_tier == SubscriptionTier.free
    assert user.paystack_subscription_code is None
    assert user.paystack_email_token is None


def test_a_disable_for_a_superseded_subscription_is_ignored(client):
    """Someone who cancels Pro and immediately buys Elite gets a late disable
    event for the old subscription. Acting on it would revoke the upgrade they
    just paid for."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id, code="SUB_new", plan_code=settings.PAYSTACK_PLAN_ELITE))

    _signed(client, {
        "event": "subscription.disable",
        "data": {
            "subscription_code": "SUB_old",
            "customer": {"customer_code": "CUS_abc", "email": "billing@example.com"},
        },
    })

    assert _reload(user_id).subscription_tier == SubscriptionTier.elite


def test_a_renewal_charge_tops_credits_back_up(client):
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id))

    _signed(client, {
        "event": "charge.success",
        "data": {
            "plan": {"plan_code": settings.PAYSTACK_PLAN_PRO},
            "customer": {"customer_code": "CUS_abc", "email": "billing@example.com"},
        },
    })

    assert _reload(user_id).ai_credits == 10 + 100 + 100


def test_a_charge_for_a_tier_the_user_is_not_on_grants_nothing(client):
    """The first charge of a subscription arrives alongside subscription.create.
    Granting on both would hand out two months of credits for one payment."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    _signed(client, {
        "event": "charge.success",
        "data": {
            "plan": {"plan_code": settings.PAYSTACK_PLAN_PRO},
            "customer": {"customer_code": "CUS_abc", "email": "billing@example.com"},
        },
    })

    assert _reload(user_id).ai_credits == 10


def test_a_one_off_charge_is_not_treated_as_a_renewal(client):
    """Paystack sends plan: [] rather than an object for non-subscription
    charges, which would blow up a naive .get on it."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id))

    resp = _signed(client, {
        "event": "charge.success",
        "data": {"plan": [], "customer": {"customer_code": "CUS_abc", "email": "billing@example.com"}},
    })

    assert resp.status_code == 200
    assert _reload(user_id).ai_credits == 10 + 100


def test_a_failed_renewal_does_not_downgrade_immediately(client):
    """Paystack retries for days before disabling. Cutting access on the first
    failure punishes a card that just needed a second attempt."""
    data = register_user(client, email="billing@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id))

    _signed(client, {
        "event": "invoice.payment_failed",
        "data": {"customer": {"customer_code": "CUS_abc", "email": "billing@example.com"}},
    })

    assert _reload(user_id).subscription_tier == SubscriptionTier.pro


def test_an_unknown_event_type_is_accepted_and_ignored(client):
    """Paystack adds event types over time; a 500 on an unrecognised one would
    make it retry forever and eventually disable the endpoint."""
    data = register_user(client, email="billing@example.com")
    resp = _signed(client, {"event": "customeridentification.success", "data": {"customer": {}}})
    assert resp.status_code == 200


def test_an_event_for_an_unknown_customer_is_not_an_error(client):
    resp = _signed(client, {
        "event": "subscription.create",
        "data": {
            "subscription_code": "SUB_x",
            "plan": {"plan_code": settings.PAYSTACK_PLAN_PRO},
            "customer": {"customer_code": "CUS_nobody", "email": "nobody@example.com"},
        },
    })
    assert resp.status_code == 200


def test_a_user_is_found_by_customer_code_when_metadata_is_absent(client):
    """Renewal events carry no metadata of ours — only the customer."""
    data = register_user(client, email="bycode@example.com")
    user_id = uuid.UUID(data["user"]["id"])

    session = SessionLocal()
    session.get(User, user_id).paystack_customer_code = "CUS_known"
    session.commit()
    session.close()

    event = {
        "event": "subscription.create",
        "data": {
            "subscription_code": "SUB_1",
            "email_token": "tok",
            "plan": {"plan_code": settings.PAYSTACK_PLAN_PRO},
            "customer": {"customer_code": "CUS_known", "email": "changed-in-paystack@example.com"},
        },
    }
    _signed(client, event)

    assert _reload(user_id).subscription_tier == SubscriptionTier.pro


# ---------- checkout and management endpoints ----------

@patch("app.services.billing.paystack.create_customer", return_value="CUS_new")
@patch("app.services.billing.paystack.initialize_transaction", return_value="https://checkout.paystack.com/abc")
def test_checkout_creates_a_customer_once_and_returns_the_payment_url(mock_init, mock_customer, client):
    data = register_user(client, email="checkout@example.com")
    headers = auth_headers(data["access_token"])

    resp = client.post("/api/billing/checkout-session", json={"tier": "pro"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.paystack.com/abc"
    assert _reload(uuid.UUID(data["user"]["id"])).paystack_customer_code == "CUS_new"

    client.post("/api/billing/checkout-session", json={"tier": "pro"}, headers=headers)
    mock_customer.assert_called_once()  # reused, not recreated


@patch("app.services.billing.paystack.create_customer", return_value="CUS_new")
def test_checkout_rejects_a_tier_with_no_plan_configured(mock_customer, client, monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_ELITE", "")
    data = register_user(client, email="noplan@example.com")

    resp = client.post(
        "/api/billing/checkout-session", json={"tier": "elite"}, headers=auth_headers(data["access_token"])
    )
    assert resp.status_code == 400


@patch("app.services.billing.paystack.create_customer", side_effect=PaystackError("Paystack is down"))
def test_a_paystack_outage_is_reported_as_a_gateway_error(mock_customer, client):
    """Not a 500 — the failure is upstream, and the message must not leak
    whatever Paystack said back to the user."""
    data = register_user(client, email="outage@example.com")

    resp = client.post(
        "/api/billing/checkout-session", json={"tier": "pro"}, headers=auth_headers(data["access_token"])
    )
    assert resp.status_code == 502
    assert "Paystack is down" not in resp.text


def test_the_portal_404s_for_a_user_with_no_subscription(client):
    data = register_user(client, email="nosub@example.com")
    resp = client.get("/api/billing/portal", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 404


def test_cancelling_leaves_the_tier_alone_until_the_period_ends(client):
    """Paystack keeps a cancelled subscription live until the paid period runs
    out, and the disable webhook fires then. Downgrading now would take away
    time already paid for."""
    data = register_user(client, email="cancel@example.com")
    user_id = uuid.UUID(data["user"]["id"])
    _signed(client, _subscription_event(user_id))

    with patch("app.services.billing.paystack.disable_subscription") as mock_disable:
        resp = client.post("/api/billing/cancel", headers=auth_headers(data["access_token"]))

    assert resp.status_code == 204
    mock_disable.assert_called_once_with(subscription_code="SUB_abc", email_token="tok_abc")
    assert _reload(user_id).subscription_tier == SubscriptionTier.pro


def test_status_reports_the_tier_and_whether_there_is_anything_to_manage(client):
    data = register_user(client, email="status@example.com")
    headers = auth_headers(data["access_token"])

    body = client.get("/api/billing/status", headers=headers).json()
    assert body["tier"] == "free"
    assert body["has_subscription"] is False
    assert body["currency"] == settings.BILLING_CURRENCY
    assert {p["tier"] for p in body["plans"]} == {"pro", "elite"}
    assert all(p["available"] for p in body["plans"])

    _signed(client, _subscription_event(uuid.UUID(data["user"]["id"])))
    assert client.get("/api/billing/status", headers=headers).json()["has_subscription"] is True


def test_status_marks_a_tier_with_no_plan_code_unavailable(client, monkeypatch):
    """Offering a buy button that can only ever return a 400 wastes the one
    moment a user was willing to pay."""
    monkeypatch.setattr(settings, "PAYSTACK_PLAN_ELITE", "")
    data = register_user(client, email="unavailable@example.com")

    plans = client.get("/api/billing/status", headers=auth_headers(data["access_token"])).json()["plans"]
    by_tier = {p["tier"]: p for p in plans}
    assert by_tier["pro"]["available"] is True
    assert by_tier["elite"]["available"] is False
