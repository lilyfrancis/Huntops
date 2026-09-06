"""The supply side: admin-owned mailboxes feeding one shared job pool."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app.core.crypto import encrypt
from app.models.alert_mailbox import AlertMailbox
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobLane, UserRole
from app.models.job import Job
from app.models.user import User
from app.schemas.ai import ExtractedJobPosting
from app.services import alert_mailboxes
from tests.conftest import auth_headers, register_user

LINKEDIN_MESSAGE = {
    "payload": {
        "headers": [{"name": "From", "value": "LinkedIn <jobalerts-noreply@linkedin.com>"}],
        "mimeType": "text/plain",
        "body": {"data": "ZmFrZSBib2R5IHRleHQ="},  # "fake body text"
    }
}


def _seed_mailbox(session, market="Canada", lanes=None, expires_in_minutes=60) -> AlertMailbox:
    mailbox = AlertMailbox(
        email_address=f"alerts-{market.lower()}@huntops.site",
        label=f"{market} alerts",
        market=market,
        lanes=lanes or [],
        access_token_encrypted=encrypt("fake-access-token"),
        refresh_token_encrypted=encrypt("fake-refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        label_id="Label_1",
    )
    session.add(mailbox)
    session.commit()
    session.refresh(mailbox)
    return mailbox


def _make_admin(client, email="mailbox-admin@example.com"):
    from app.db.base import SessionLocal

    register_user(client, email=email)
    session = SessionLocal()
    session.query(User).filter(User.email == email).first().role = UserRole.admin
    session.commit()
    session.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": "StrongPass1"})
    return auth_headers(resp.json()["access_token"])


# ---------- sync ----------

def test_sync_tags_ingested_jobs_with_the_mailbox_market(db_session):
    """The whole point of the central design: a job knows which market's
    mailbox it arrived through, so a user's country filter can trust it."""
    mailbox = _seed_mailbox(db_session, market="Canada")
    postings = [ExtractedJobPosting(title="Backend Engineer", company="Acme", url=None, location=None)]

    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.alert_mailboxes.gmail_oauth.get_message", return_value=LINKEDIN_MESSAGE), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=postings):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["status"] == "success"
    assert summary["inserted"] == 1

    job = db_session.query(Job).filter(Job.source == "email-linkedin").one()
    assert job.market == "Canada"
    assert job.location == "Canada"  # posting had none; the market is the honest default
    assert "linkedin.com/jobs/search" in job.source_url  # no url in posting -> stable fallback

    run = db_session.query(EmailSyncRun).filter(EmailSyncRun.mailbox_id == mailbox.id).one()
    assert run.status == "success"
    assert run.user_id is None


def test_sync_skips_urls_already_in_the_pool(db_session):
    """Supply is shared, so the same posting can arrive through two mailboxes.
    It must land once."""
    mailbox = _seed_mailbox(db_session)
    db_session.add(Job(
        title="Backend Engineer", description="desc", requirements=[], location="Remote",
        job_type="full_time", experience_level="mid", source="remotive",
        source_url="https://acme.example/job/1",
    ))
    db_session.commit()

    postings = [ExtractedJobPosting(
        title="Backend Engineer", company="Acme", url="https://acme.example/job/1", location="Remote"
    )]
    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.alert_mailboxes.gmail_oauth.get_message", return_value=LINKEDIN_MESSAGE), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=postings):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["extracted"] == 1
    assert summary["inserted"] == 0


def test_a_single_lane_mailbox_labels_jobs_inference_gave_up_on(db_session):
    mailbox = _seed_mailbox(db_session, market="Canada", lanes=[JobLane.marketing.value])
    postings = [ExtractedJobPosting(title="Zonal Coordinator", company="Acme", url=None, location=None)]

    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.alert_mailboxes.gmail_oauth.get_message", return_value=LINKEDIN_MESSAGE), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=postings):
        alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert db_session.query(Job).one().lane == JobLane.marketing


def test_the_listing_beats_the_mailbox_label_when_inference_matches(db_session):
    """A marketing alert digest routinely carries one engineering role. The
    job's own title has to win, or that role is filed under the wrong lane."""
    mailbox = _seed_mailbox(db_session, market="Canada", lanes=[JobLane.marketing.value])
    postings = [ExtractedJobPosting(title="Senior Software Engineer", company="Acme", url=None, location=None)]

    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.alert_mailboxes.gmail_oauth.get_message", return_value=LINKEDIN_MESSAGE), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=postings):
        alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert db_session.query(Job).one().lane == JobLane.engineering


def test_a_failing_mailbox_records_the_error_instead_of_raising(db_session):
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", side_effect=RuntimeError("Gmail API down")):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["status"] == "error"
    assert "Gmail API down" in summary["error"]
    db_session.refresh(mailbox)
    assert "Gmail API down" in mailbox.last_error


def test_one_broken_mailbox_does_not_stop_the_others(db_session):
    """The failure mode that matters operationally: a revoked grant on one
    market must not silently starve every other market's feed."""
    _seed_mailbox(db_session, market="Canada")
    _seed_mailbox(db_session, market="UK")

    def _list(access_token, label_id, query):
        raise RuntimeError("Gmail API down")

    with patch("app.services.alert_mailboxes.gmail_oauth.list_message_ids", side_effect=_list):
        results = alert_mailboxes.sync_all_mailboxes(db_session)

    assert len(results) == 2
    assert {r["status"] for r in results} == {"error"}


def test_inactive_mailboxes_are_not_synced(db_session):
    mailbox = _seed_mailbox(db_session)
    mailbox.is_active = False
    db_session.commit()

    assert alert_mailboxes.sync_all_mailboxes(db_session) == []


def test_known_markets_only_lists_markets_with_live_supply(db_session):
    _seed_mailbox(db_session, market="Canada")
    dormant = _seed_mailbox(db_session, market="UK")
    dormant.is_active = False
    db_session.commit()

    assert alert_mailboxes.known_markets(db_session) == ["Canada"]


# ---------- admin API ----------

def test_mailbox_endpoints_require_admin(client):
    data = register_user(client, email="seeker-no-mailboxes@example.com")
    resp = client.get("/api/admin/mailboxes", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_connect_signs_the_market_into_the_oauth_state(client):
    """The market is chosen before the consent screen and has to survive the
    round trip through Google — signed, so the browser can't rewrite it."""
    headers = _make_admin(client)
    resp = client.post(
        "/api/admin/mailboxes/connect",
        json={"market": "Canada", "label": "Canada alerts", "lanes": ["marketing"]},
        headers=headers,
    )
    assert resp.status_code == 200

    state = parse_qs(urlparse(resp.json()["authorization_url"]).query)["state"][0]

    from app.core.security import decode_token, TokenType
    payload = decode_token(state, TokenType.oauth_state)
    assert payload["purpose"] == "admin_mailbox"
    assert payload["market"] == "Canada"
    assert payload["lanes"] == ["marketing"]


def test_connect_rejects_a_blank_market(client):
    headers = _make_admin(client, email="blank-market-admin@example.com")
    resp = client.post("/api/admin/mailboxes/connect", json={"market": "   "}, headers=headers)
    assert resp.status_code == 422


def test_connect_rejects_an_unknown_lane(client):
    headers = _make_admin(client, email="bad-lane-admin@example.com")
    resp = client.post(
        "/api/admin/mailboxes/connect", json={"market": "Canada", "lanes": ["astrology"]}, headers=headers
    )
    assert resp.status_code == 422


def test_a_non_admin_state_cannot_attach_a_mailbox(client):
    """The signed state proves who started the flow; the callback still
    re-checks the role, so a seeker who somehow obtained an admin-purpose
    state can't attach a mailbox to everyone's feed."""
    from app.core.security import create_oauth_state_token, OAuthPurpose
    from app.db.base import SessionLocal

    register_user(client, email="not-admin-mailbox@example.com")
    session = SessionLocal()
    user = session.query(User).filter(User.email == "not-admin-mailbox@example.com").first()
    state = create_oauth_state_token(user.id, OAuthPurpose.admin_mailbox, market="Canada", label=None, lanes=[])
    session.close()

    resp = client.get(
        "/api/integrations/gmail/callback",
        params={"code": "google-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307)
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["mailbox"] == ["error"]
    assert "admin" in query["message"][0]


def test_listing_updating_and_deleting_a_mailbox(client, db_session):
    headers = _make_admin(client, email="crud-admin@example.com")
    mailbox = _seed_mailbox(db_session, market="Canada")

    resp = client.get("/api/admin/mailboxes", headers=headers)
    assert resp.status_code == 200
    assert [m["market"] for m in resp.json()] == ["Canada"]

    resp = client.patch(
        f"/api/admin/mailboxes/{mailbox.id}", json={"market": "UK", "is_active": False}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["market"] == "UK"
    assert resp.json()["is_active"] is False

    with patch("app.services.alert_mailboxes.gmail_oauth.revoke_token") as mock_revoke:
        resp = client.delete(f"/api/admin/mailboxes/{mailbox.id}", headers=headers)
    assert resp.status_code == 204
    mock_revoke.assert_called_once()
    assert db_session.query(AlertMailbox).count() == 0


def test_deleting_a_mailbox_keeps_the_jobs_it_ingested(client, db_session):
    """Those are real listings people may already be matched to — deleting a
    mailbox must not empty their feed."""
    headers = _make_admin(client, email="delete-admin@example.com")
    mailbox = _seed_mailbox(db_session, market="Canada")
    db_session.add(Job(
        title="Backend Engineer", description="desc", requirements=[], location="Toronto",
        job_type="full_time", experience_level="mid", source="email-linkedin",
        source_url="https://acme.example/job/9", market="Canada",
    ))
    db_session.commit()

    with patch("app.services.alert_mailboxes.gmail_oauth.revoke_token"):
        client.delete(f"/api/admin/mailboxes/{mailbox.id}", headers=headers)

    assert db_session.query(Job).count() == 1


# ---------- connecting without the optional settings scope ----------

def _connect(db_session, admin_id, *, filters_ok: bool):
    with patch("app.services.alert_mailboxes.gmail_oauth.exchange_code_for_tokens",
               return_value={"access_token": "a", "refresh_token": "r", "expires_in": 3600}), \
         patch("app.services.alert_mailboxes.gmail_oauth.get_profile_email",
               return_value="alerts-new@huntops.site"), \
         patch("app.services.alert_mailboxes.gmail_oauth.ensure_label", return_value="Label_9"), \
         patch("app.services.alert_mailboxes.gmail_oauth.ensure_filter", return_value=filters_ok):
        return alert_mailboxes.connect_from_oauth_code(
            db_session, code="c", admin_id=admin_id, market="Canada", label=None, lanes=[]
        )


def test_a_mailbox_whose_filters_failed_says_what_to_do_about_it(db_session):
    """gmail.settings.basic is restricted, so declining it is a legitimate
    choice — but then nothing lands under the label and the mailbox finds no
    jobs. It has to say so, and say how to fix it by hand."""
    admin = User(email="filter-admin@example.com", password_hash="x", full_name="A", role=UserRole.admin)
    db_session.add(admin)
    db_session.flush()

    mailbox = _connect(db_session, admin.id, filters_ok=False)

    assert mailbox.last_error is not None
    assert "linkedin.com" in mailbox.last_error
    assert "add a filter" in mailbox.last_error
    assert "no jobs" in mailbox.last_error


def test_a_mailbox_whose_filters_worked_carries_no_error(db_session):
    admin = User(email="ok-admin@example.com", password_hash="x", full_name="A", role=UserRole.admin)
    db_session.add(admin)
    db_session.flush()

    assert _connect(db_session, admin.id, filters_ok=True).last_error is None
