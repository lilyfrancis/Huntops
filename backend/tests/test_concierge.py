"""Applying on a user's behalf to a site we cannot submit to.

The product exists to remove the rigorous part of a job hunt — opening
thirty tabs and retyping the same details into thirty forms. Handing back a
link for every external listing is handing that work straight back.
"""

import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.models.application import Application
from app.models.enums import ApplicationStatus, ConciergeStatus, SubscriptionTier, UserRole
from app.models.user import User
from app.services import concierge
from tests.conftest import auth_headers, register_user
from tests.test_outreach import _elite_user_with_resume, _job

settings = get_settings()


@pytest.fixture
def elite(db_session):
    from app.core.security import hash_password

    user = _elite_user_with_resume(db_session, email="elite-concierge@example.com", credits=500)
    user.password_hash = hash_password("StrongPass1")
    db_session.commit()
    return user


@pytest.fixture
def free_user(db_session):
    from app.core.security import hash_password
    from app.models.resume import Resume

    user = User(
        email="free-concierge@example.com", password_hash=hash_password("StrongPass1"),
        full_name="Jennifer Okafor", role=UserRole.job_seeker,
        subscription_tier=SubscriptionTier.free, ai_credits=500,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Resume(user_id=user.id, raw_text="x", parsed_skills=["Growth"], experience_years=4))
    db_session.commit()
    return user


def _external(db_session, n=0):
    return _job(db_session, title=f"External Role {n}", source="email-linkedin",
                source_url=f"https://weworkremotely.test/{n}")


def _login(client, email):
    token = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"}).json()
    return auth_headers(token["access_token"])


# ---------- requesting ----------

def test_applying_to_an_external_job_queues_it_instead_of_refusing(client, db_session, elite):
    job = _external(db_session)
    resp = client.post("/api/applications", json={"job_id": str(job.id)},
                       headers=_login(client, elite.email))

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_concierge"] is True
    assert body["concierge_status"] == "queued"
    # Not "submitted": nobody has filed it yet, and saying otherwise would be
    # the one lie this feature cannot afford.
    assert body["submitted_at"] is None


def test_an_internal_job_still_applies_directly(client, db_session, elite):
    """The concierge path must not swallow the case that already worked."""
    job = _job(db_session, title="Internal Role", source="internal")
    resp = client.post("/api/applications", json={"job_id": str(job.id)},
                       headers=_login(client, elite.email))

    assert resp.status_code == 201
    assert resp.json()["is_concierge"] is False


def test_the_tailored_letter_goes_into_the_queue_with_it(client, db_session, elite):
    """The admin filing it should not have to go and find the letter."""
    from app.models.application_draft import ApplicationDraft

    job = _external(db_session)
    db_session.add(ApplicationDraft(
        user_id=elite.id, job_id=job.id,
        cover_letter="Hello, I have run growth for six years.",
        bullets=["Grew pipeline 4.5x"],
    ))
    db_session.commit()

    client.post("/api/applications", json={"job_id": str(job.id)}, headers=_login(client, elite.email))

    application = db_session.query(Application).one()
    assert application.cover_letter.startswith("Hello,")
    assert application.tailored_bullets == ["Grew pipeline 4.5x"]


def test_requesting_costs_credits(client, db_session, elite):
    before = elite.ai_credits
    client.post("/api/applications", json={"job_id": str(_external(db_session).id)},
                headers=_login(client, elite.email))

    db_session.refresh(elite)
    assert elite.ai_credits == before - settings.CONCIERGE_CREDIT_COST


# ---------- who may use it ----------

def test_a_free_user_gets_a_small_allowance_then_a_clear_wall(client, db_session, free_user):
    headers = _login(client, free_user.email)

    for n in range(settings.CONCIERGE_FREE_ALLOWANCE):
        resp = client.post("/api/applications", json={"job_id": str(_external(db_session, n).id)},
                           headers=headers)
        assert resp.status_code == 201, resp.json()

    resp = client.post("/api/applications", json={"job_id": str(_external(db_session, 99).id)},
                       headers=headers)
    assert resp.status_code == 403
    assert "Elite" in resp.json()["detail"]


def test_elite_is_bounded_by_credits_rather_than_a_count(db_session, elite):
    assert concierge.allowance_remaining(db_session, elite) is None


def test_running_out_of_credits_refuses_before_charging(client, db_session, elite):
    elite.ai_credits = 5
    db_session.commit()

    resp = client.post("/api/applications", json={"job_id": str(_external(db_session).id)},
                       headers=_login(client, elite.email))

    assert resp.status_code == 402
    db_session.refresh(elite)
    assert elite.ai_credits == 5           # nothing taken
    assert db_session.query(Application).count() == 0   # nothing queued


def test_the_allowance_is_readable_before_clicking(client, db_session, free_user):
    """A button that charges and then refuses is worse than one that says
    what it will cost."""
    body = client.get("/api/applications/concierge/allowance",
                      headers=_login(client, free_user.email)).json()

    assert body["remaining"] == settings.CONCIERGE_FREE_ALLOWANCE
    assert body["credit_cost"] == settings.CONCIERGE_CREDIT_COST


# ---------- the admin side ----------

def test_the_queue_carries_everything_needed_to_file_it(client, db_session, free_user):
    job = _external(db_session)
    client.post("/api/applications", json={"job_id": str(job.id)},
                headers=_login(client, free_user.email))

    from tests.test_alert_mailboxes import _make_admin
    rows = client.get("/api/admin/concierge", headers=_make_admin(client, "queue@example.com")).json()

    assert len(rows) == 1
    row = rows[0]
    assert row["source_url"] == job.source_url          # where to go
    assert row["candidate_name"] == "Jennifer Okafor"
    assert row["suggested_concierge_email"] == "jennifer@huntops.site"
    assert row["concierge_email"] is None               # not created yet


def test_marking_it_submitted_records_who_and_when(client, db_session, free_user):
    job = _external(db_session)
    app_id = client.post("/api/applications", json={"job_id": str(job.id)},
                         headers=_login(client, free_user.email)).json()["id"]

    from tests.test_alert_mailboxes import _make_admin
    headers = _make_admin(client, "filer@example.com")
    resp = client.patch(f"/api/admin/concierge/{app_id}", headers=headers, json={
        "concierge_status": "submitted",
        "concierge_email": "jennifer@huntops.site",
    })

    assert resp.status_code == 200
    assert resp.json()["concierge_status"] == "submitted"
    assert resp.json()["submitted_at"] is not None

    db_session.expire_all()
    assert db_session.get(User, free_user.id).concierge_email == "jennifer@huntops.site"
    assert db_session.get(Application, uuid.UUID(resp.json()["id"])).handled_by_id is not None


def test_a_listing_that_cannot_be_filed_says_why_in_the_users_words(client, db_session, free_user):
    job = _external(db_session)
    app_id = client.post("/api/applications", json={"job_id": str(job.id)},
                         headers=_login(client, free_user.email)).json()["id"]

    from tests.test_alert_mailboxes import _make_admin
    client.patch(f"/api/admin/concierge/{app_id}", headers=_make_admin(client, "blocker@example.com"),
                 json={"concierge_status": "blocked", "note": "The listing was taken down."})

    mine = client.get("/api/applications/mine", headers=_login(client, free_user.email)).json()
    assert mine[0]["concierge_status"] == "blocked"
    assert mine[0]["concierge_note"] == "The listing was taken down."


def test_employer_progress_reaches_the_user(client, db_session, free_user):
    """Replies go to the address we applied under, not the user's inbox, so
    an admin relaying them is the only way the user ever hears."""
    job = _external(db_session)
    app_id = client.post("/api/applications", json={"job_id": str(job.id)},
                         headers=_login(client, free_user.email)).json()["id"]

    from tests.test_alert_mailboxes import _make_admin
    client.patch(f"/api/admin/concierge/{app_id}/status",
                 headers=_make_admin(client, "relay@example.com"),
                 json={"status": "interviewing", "note": "They want a call on Thursday."})

    mine = client.get("/api/applications/mine", headers=_login(client, free_user.email)).json()
    assert mine[0]["status"] == ApplicationStatus.interviewing.value
    assert "Thursday" in mine[0]["concierge_note"]


def test_the_queue_shows_only_what_is_waiting_by_default(client, db_session, free_user):
    from tests.test_alert_mailboxes import _make_admin

    headers = _login(client, free_user.email)
    done_id = client.post("/api/applications", json={"job_id": str(_external(db_session, 1).id)},
                          headers=headers).json()["id"]
    client.post("/api/applications", json={"job_id": str(_external(db_session, 2).id)}, headers=headers)

    admin = _make_admin(client, "filter@example.com")
    client.patch(f"/api/admin/concierge/{done_id}", headers=admin,
                 json={"concierge_status": "submitted"})

    assert len(client.get("/api/admin/concierge", headers=admin).json()) == 1
    assert len(client.get("/api/admin/concierge?status=submitted", headers=admin).json()) == 1


# ---------- telling an admin there is work ----------

def test_an_admin_is_told_the_moment_a_request_arrives(client, db_session, elite):
    """The queue only updates when somebody opens it. A request nobody knows
    about is a user watching "queued" for a day."""
    job = _external(db_session)

    with patch("app.services.concierge.notifications.alert_admin") as alert:
        client.post("/api/applications", json={"job_id": str(job.id)},
                    headers=_login(client, elite.email))

    alert.assert_called_once()
    subject, body = alert.call_args.args
    assert "Elite User" in subject and job.title in subject
    assert job.source_url in body            # where to go
    assert "/admin/concierge" in body        # and where to mark it done


def test_the_suggested_address_is_flagged_as_not_yet_created(client, db_session, free_user):
    job = _external(db_session)
    with patch("app.services.concierge.notifications.alert_admin") as alert:
        client.post("/api/applications", json={"job_id": str(job.id)},
                    headers=_login(client, free_user.email))

    body = alert.call_args.args[1]
    assert "jennifer@huntops.site" in body
    assert "not created yet" in body


def test_a_failed_notification_does_not_fail_the_request(client, db_session, elite):
    """The request is the user's; a mail server being down is ours. Rolling
    back a paid-for request over our outage would be charging for it."""
    job = _external(db_session)
    before = elite.ai_credits

    with patch("app.services.concierge.notifications.alert_admin",
               side_effect=RuntimeError("smtp down")):
        resp = client.post("/api/applications", json={"job_id": str(job.id)},
                           headers=_login(client, elite.email))

    assert resp.status_code == 201
    assert db_session.query(Application).count() == 1
    db_session.refresh(elite)
    assert elite.ai_credits == before - settings.CONCIERGE_CREDIT_COST


def test_notifications_can_be_turned_off(client, db_session, elite, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFY_ADMIN_ON_CONCIERGE", False)
    with patch("app.services.concierge.notifications.alert_admin") as alert:
        client.post("/api/applications", json={"job_id": str(_external(db_session).id)},
                    headers=_login(client, elite.email))
    alert.assert_not_called()


# ---------- chasing a backlog ----------

def test_a_request_past_the_sla_is_chased(client, db_session, elite):
    from datetime import datetime, timedelta, timezone

    job = _external(db_session)
    with patch("app.services.concierge.notifications.alert_admin"):
        client.post("/api/applications", json={"job_id": str(job.id)},
                    headers=_login(client, elite.email))

    application = db_session.query(Application).one()
    application.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db_session.commit()

    with patch("app.services.concierge.notifications.alert_admin") as alert:
        assert concierge.alert_on_backlog(db_session) == 1

    assert "still waiting" in alert.call_args.args[0]


def test_a_current_queue_says_nothing(client, db_session, elite):
    """A daily "nothing to do" mail is how a daily alert stops being read,
    and this one has to be read."""
    with patch("app.services.concierge.notifications.alert_admin"):
        client.post("/api/applications", json={"job_id": str(_external(db_session).id)},
                    headers=_login(client, elite.email))

    with patch("app.services.concierge.notifications.alert_admin") as alert:
        assert concierge.alert_on_backlog(db_session) == 0   # queued, but not yet overdue
    alert.assert_not_called()


def test_something_already_filed_is_not_chased(client, db_session, elite):
    from datetime import datetime, timedelta, timezone
    from tests.test_alert_mailboxes import _make_admin

    with patch("app.services.concierge.notifications.alert_admin"):
        app_id = client.post("/api/applications", json={"job_id": str(_external(db_session).id)},
                             headers=_login(client, elite.email)).json()["id"]

    application = db_session.query(Application).one()
    application.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db_session.commit()

    client.patch(f"/api/admin/concierge/{app_id}", headers=_make_admin(client, "done@example.com"),
                 json={"concierge_status": "submitted"})

    with patch("app.services.concierge.notifications.alert_admin") as alert:
        assert concierge.alert_on_backlog(db_session) == 0
    alert.assert_not_called()
