"""Accounts exempt from charging.

The operator has to be able to use the product without buying from
themselves. The risk in a feature like this is not that it fails to work —
it is that it works in six places and not the seventh, so the checks all go
through one helper and this covers that helper plus the paths that matter.
"""

import uuid

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models.credit_ledger import CreditLedgerEntry
from app.models.user import User
from app.services.credits import adjust_credits, can_afford
from tests.conftest import auth_headers, register_user

settings = get_settings()


def _user(**kw) -> User:
    return User(email=f"{uuid.uuid4()}@example.com", password_hash="x", full_name="T",
                role="job_seeker", **kw)


def test_an_exempt_account_can_afford_what_it_cannot_pay_for():
    assert can_afford(_user(ai_credits=0, unlimited_credits=True), 500) is True


def test_an_ordinary_account_still_cannot():
    assert can_afford(_user(ai_credits=4, unlimited_credits=False), 5) is False
    assert can_afford(_user(ai_credits=5, unlimited_credits=False), 5) is True


def test_spending_does_not_move_an_exempt_balance(db_session):
    user = _user(ai_credits=100, unlimited_credits=True)
    db_session.add(user)
    db_session.flush()

    adjust_credits(db_session, user, action="unlock_job", amount=-5)
    db_session.commit()

    assert user.ai_credits == 100


def test_the_action_is_still_recorded_at_zero(db_session):
    """The ledger is how usage is reviewed. An exempt account that writes
    nothing is invisible in that review, which is worse than a zero row."""
    user = _user(ai_credits=100, unlimited_credits=True)
    db_session.add(user)
    db_session.flush()

    adjust_credits(db_session, user, action="concierge_apply", amount=-15)
    db_session.commit()

    entry = db_session.query(CreditLedgerEntry).filter(CreditLedgerEntry.user_id == user.id).one()
    assert entry.action == "concierge_apply"
    assert entry.amount == 0
    assert entry.balance_after == 100


def test_granting_credits_to_an_exempt_account_still_works(db_session):
    """Only spends are exempt. A grant — a plan renewal, a refund — is a
    deliberate act and should land, or the ledger stops reconciling."""
    user = _user(ai_credits=10, unlimited_credits=True)
    db_session.add(user)
    db_session.flush()

    adjust_credits(db_session, user, action="plan_renewal", amount=300)
    db_session.commit()

    assert user.ai_credits == 310


def test_an_exempt_account_unlocks_without_paying(client):
    """End to end through the real endpoint, because the point of the flag is
    the eighth call site nobody remembered."""
    from app.models.enums import ExperienceLevel, JobStatus, JobType
    from app.models.job import Job

    data = register_user(client, email="exempt-unlock@example.com")
    session = SessionLocal()
    try:
        user = session.get(User, uuid.UUID(data["user"]["id"]))
        user.unlimited_credits = True
        user.ai_credits = 0
        job = Job(title="Head of Growth", description="d", requirements=[], location="Lagos, Nigeria",
                  job_type=JobType.full_time, experience_level=ExperienceLevel.senior,
                  source="email-linkedin", source_url="https://x.test/exempt", status=JobStatus.active,
                  company_name="Paystack")
        session.add(job)
        session.commit()
        job_id = str(job.id)
    finally:
        session.close()

    resp = client.post(f"/api/jobs/{job_id}/unlock", headers=auth_headers(data["access_token"]))

    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["company_name"] == "Paystack"


def test_the_flag_is_served_so_the_wallet_can_say_so(client):
    data = register_user(client, email="exempt-me@example.com")
    session = SessionLocal()
    try:
        session.get(User, uuid.UUID(data["user"]["id"])).unlimited_credits = True
        session.commit()
    finally:
        session.close()

    body = client.get("/api/auth/me", headers=auth_headers(data["access_token"])).json()

    assert body["unlimited_credits"] is True
