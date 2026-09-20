"""Credits, not the plan, decide what a user can see — and buying more.

Tier-locking meant a paying Pro customer met a wall they could not pay
past. One gate, one thing to buy, and no plan that is a different set of
walls rather than a different number of credits.
"""

from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.models.credit_ledger import CreditLedgerEntry
from app.models.enums import JobStatus, SubscriptionTier, UserRole
from app.models.job_unlock import JobUnlock
from app.models.user import User
from app.schemas.job import job_out_for
from app.services import billing as billing_service
from app.services import unlocking
from tests.conftest import auth_headers, register_user
from tests.test_outreach import _job

settings = get_settings()


@pytest.fixture
def external(db_session):
    return _job(db_session, title="Director of Sales, New Logo", source="weworkremotely",
                source_url="https://weworkremotely.com/jobs/1", company_name="Temporal Technologies",
                salary_range="$140k", status=JobStatus.active)


def _seeker(db_session, tier=SubscriptionTier.free, credits=100, email="gate@example.com"):
    from app.core.security import hash_password

    user = User(email=email, password_hash=hash_password("StrongPass1"), full_name="Ada Seeker",
                role=UserRole.job_seeker, subscription_tier=tier, ai_credits=credits)
    db_session.add(user)
    db_session.commit()
    return user


# ---------- the gate is credits, for everyone ----------

@pytest.mark.parametrize("tier", [SubscriptionTier.free, SubscriptionTier.pro, SubscriptionTier.elite])
def test_every_tier_starts_locked_and_unlocks_the_same_way(db_session, external, tier):
    """Including Elite. A plan is how many credits you get, not a different
    set of walls — so there is one rule to explain and one thing to buy."""
    user = _seeker(db_session, tier, email=f"{tier.value}@example.com")

    assert job_out_for(external, user, unlocking.unlocked_ids(db_session, user)).locked is True
    unlocking.unlock(db_session, user, external)
    assert job_out_for(external, user, unlocking.unlocked_ids(db_session, user)).locked is False


def test_unlocking_spends_credits_once(db_session, external):
    """Charging again to re-read a listing they paid for would make people
    afraid to click, which is the opposite of what a paid unlock is for."""
    user = _seeker(db_session, credits=100)

    assert unlocking.unlock(db_session, user, external) is True
    assert unlocking.unlock(db_session, user, external) is False   # already theirs

    db_session.refresh(user)
    assert user.ai_credits == 100 - settings.UNLOCK_CREDIT_COST
    assert db_session.query(JobUnlock).count() == 1


def test_running_out_of_credits_refuses_without_charging(db_session, external):
    user = _seeker(db_session, credits=1)

    with pytest.raises(unlocking.InsufficientCredits):
        unlocking.unlock(db_session, user, external)

    db_session.refresh(user)
    assert user.ai_credits == 1
    assert db_session.query(JobUnlock).count() == 0


def test_internal_jobs_cost_nothing_to_see(db_session):
    """Nothing to route around: they apply through us either way."""
    internal = _job(db_session, title="Internal", source="internal", company_name="Acme")
    user = _seeker(db_session, credits=100)

    assert unlocking.unlock(db_session, user, internal) is False
    db_session.refresh(user)
    assert user.ai_credits == 100


def test_applying_unlocks_without_a_second_charge(client, db_session, external):
    """They committed and were charged for the apply. Charging again to read
    what they applied to would be charging twice for one decision."""
    user = _seeker(db_session, credits=100, email="applied@example.com")
    token = client.post("/api/auth/login",
                        json={"email": user.email, "password": "StrongPass1"}).json()

    with patch("app.services.concierge.notifications.alert_admin"):
        client.post("/api/applications", json={"job_id": str(external.id)},
                    headers=auth_headers(token["access_token"]))

    db_session.refresh(user)
    assert user.ai_credits == 100 - settings.CONCIERGE_CREDIT_COST   # the apply only
    assert job_out_for(external, user, unlocking.unlocked_ids(db_session, user)).locked is False


def test_the_unlock_route_returns_the_revealed_job(client, db_session, external):
    register_user(client, email="route@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "route@example.com", "password": "StrongPass1"}).json()
    headers = auth_headers(token["access_token"])

    body = client.post(f"/api/jobs/{external.id}/unlock", headers=headers).json()

    assert body["locked"] is False
    assert body["company_name"] == "Temporal Technologies"


def test_the_unlock_route_refuses_politely_when_broke(client, db_session, external):
    register_user(client, email="broke@example.com")
    from app.db.base import SessionLocal

    session = SessionLocal()
    session.query(User).filter(User.email == "broke@example.com").update({User.ai_credits: 1})
    session.commit()
    session.close()

    token = client.post("/api/auth/login",
                        json={"email": "broke@example.com", "password": "StrongPass1"}).json()
    resp = client.post(f"/api/jobs/{external.id}/unlock",
                       headers=auth_headers(token["access_token"]))

    assert resp.status_code == 402
    assert "credits" in resp.json()["detail"]


# ---------- buying more ----------

def test_the_packs_are_listed_publicly(client):
    """The price of more credits is part of deciding whether to subscribe,
    so it cannot sit behind a login."""
    packs = client.get("/api/billing/credit-packs").json()

    assert len(packs) >= 2
    assert packs == sorted(packs, key=lambda p: p["credits"])
    assert all(p["currency"] == settings.BILLING_CURRENCY for p in packs)


def test_bigger_packs_cost_less_per_credit(client):
    """Otherwise there is no reason to take the step up."""
    packs = client.get("/api/billing/credit-packs").json()
    rates = [p["price"] / p["credits"] for p in packs]
    assert rates == sorted(rates, reverse=True), rates


def test_buying_sends_the_credit_count_with_the_payment(client, db_session):
    """Not looked up from the pack code later: if the packs are repriced
    between opening checkout and paying, they get what they were shown."""
    register_user(client, email="buyer@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "buyer@example.com", "password": "StrongPass1"}).json()

    with patch("app.services.billing.paystack.initialize_charge",
               return_value="https://checkout.test/x") as init:
        resp = client.post("/api/billing/buy-credits", json={"pack": "starter"},
                           headers=auth_headers(token["access_token"]))

    assert resp.status_code == 200
    # Read from the configured pack rather than restated, so repricing is
    # one line and not a test edit.
    starter = next(p for p in settings.credit_packs if p["code"] == "starter")
    assert init.call_args.kwargs["metadata"]["credits"] == starter["credits"]
    assert init.call_args.kwargs["amount"] == starter["price"]


def test_an_unknown_pack_is_a_404_not_a_charge(client):
    register_user(client, email="nopack@example.com")
    token = client.post("/api/auth/login",
                        json={"email": "nopack@example.com", "password": "StrongPass1"}).json()

    with patch("app.services.billing.paystack.initialize_charge") as init:
        resp = client.post("/api/billing/buy-credits", json={"pack": "nonsense"},
                           headers=auth_headers(token["access_token"]))

    assert resp.status_code == 404
    init.assert_not_called()


def test_a_paid_pack_grants_credits(db_session):
    user = _seeker(db_session, credits=10, email="topup@example.com")

    billing_service.handle_charge_success(db_session, {
        "reference": "ref_abc123",
        "customer": {"email": user.email},
        "metadata": {"user_id": str(user.id), "credits": 100, "pack": "starter"},
    })

    db_session.refresh(user)
    assert user.ai_credits == 110


def test_the_same_payment_cannot_grant_twice(db_session):
    """Paystack retries a webhook it did not get a 200 for, and can deliver
    the same event twice on its own. Granting twice is money given away."""
    user = _seeker(db_session, credits=10, email="replay@example.com")
    event = {
        "reference": "ref_replay",
        "customer": {"email": user.email},
        "metadata": {"user_id": str(user.id), "credits": 100},
    }

    billing_service.handle_charge_success(db_session, event)
    billing_service.handle_charge_success(db_session, event)
    billing_service.handle_charge_success(db_session, event)

    db_session.refresh(user)
    assert user.ai_credits == 110
    grants = db_session.query(CreditLedgerEntry).filter(
        CreditLedgerEntry.action == "paystack_credits:ref_replay").count()
    assert grants == 1


def test_a_charge_with_no_reference_grants_nothing(db_session):
    """Without one there is no way to tell a retry from a second purchase,
    and guessing wrong either way is worse than asking a human to look."""
    user = _seeker(db_session, credits=10, email="noref@example.com")

    billing_service.handle_charge_success(db_session, {
        "customer": {"email": user.email},
        "metadata": {"user_id": str(user.id), "credits": 100},
    })

    db_session.refresh(user)
    assert user.ai_credits == 10


def test_a_renewal_is_still_a_renewal_not_a_top_up(db_session):
    """The top-up path must not swallow subscription charges."""
    user = _seeker(db_session, credits=10, email="renewal@example.com")

    billing_service.handle_charge_success(db_session, {
        "reference": "ref_plan",
        "customer": {"email": user.email},
        "plan": {"plan_code": "PLN_unknown"},
        "metadata": {"credits": 999},
    })

    db_session.refresh(user)
    assert user.ai_credits == 10   # not granted as a pack
