"""The supply side: admin-owned IMAP mailboxes feeding one shared job pool."""

from datetime import datetime, timezone
import pytest
from unittest.mock import patch

from app.core.crypto import decrypt, encrypt
from app.models.alert_mailbox import AlertMailbox
from app.models.email_sync_run import EmailSyncRun
from app.models.enums import JobLane, UserRole
from app.models.job import Job
from app.models.user import User
from app.schemas.ai import ExtractedJobPosting
from app.services import alert_mailboxes
from app.services.imap_client import FetchedMessage, ImapError
from tests.conftest import auth_headers, register_user

LINKEDIN = "LinkedIn <jobalerts-noreply@linkedin.com>"


def _seed_mailbox(session, market="Canada", lanes=None) -> AlertMailbox:
    mailbox = AlertMailbox(
        email_address=f"alerts-{market.lower().replace(' ', '-')}@jobquickai.site",
        label=f"{market} alerts",
        market=market,
        lanes=lanes or [],
        imap_host="imap.jobquickai.site",
        imap_port=993,
        imap_username=f"alerts-{market.lower().replace(' ', '-')}@jobquickai.site",
        imap_password_encrypted=encrypt("app-password"),
        imap_use_ssl=True,
        imap_folder="INBOX",
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


def _sync(db_session, mailbox, *, messages, postings, validity=42):
    with patch("app.services.alert_mailboxes.imap_client.fetch_messages",
               return_value=(messages, validity)), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=postings):
        return alert_mailboxes.sync_mailbox(db_session, mailbox)


# ---------- sync ----------

def test_sync_tags_ingested_jobs_with_the_mailbox_market(db_session):
    """The whole point of the central design: a job knows which market's
    mailbox it arrived through, so a user's country filter can trust it."""
    mailbox = _seed_mailbox(db_session, market="Canada")
    summary = _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=7, sender=LINKEDIN, body="alert text")],
        postings=[ExtractedJobPosting(title="Backend Engineer", company="Acme", url=None, location=None)],
    )

    assert summary["status"] == "success"
    assert summary["inserted"] == 1

    job = db_session.query(Job).one()
    assert job.market == "Canada"
    assert job.location == "Canada"  # posting had none; the market is the honest default
    assert "linkedin.com/jobs/search" in job.source_url  # no url -> stable fallback

    run = db_session.query(EmailSyncRun).one()
    assert run.status == "success"
    assert run.user_id is None


def test_sync_records_the_uid_cursor_so_the_next_run_resumes(db_session):
    mailbox = _seed_mailbox(db_session)
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=11, sender=LINKEDIN, body="a"),
                  FetchedMessage(uid=14, sender=LINKEDIN, body="b")],
        postings=[],
    )

    db_session.refresh(mailbox)
    assert mailbox.last_seen_uid == 14
    assert mailbox.uid_validity == 42


def test_a_sync_that_found_nothing_leaves_the_cursor_alone(db_session):
    """Clobbering it with a null would send the next run back to a date window
    and re-extract everything inside it."""
    mailbox = _seed_mailbox(db_session)
    mailbox.last_seen_uid = 30
    db_session.commit()

    _sync(db_session, mailbox, messages=[], postings=[])

    db_session.refresh(mailbox)
    assert mailbox.last_seen_uid == 30


def test_mail_from_an_unknown_sender_is_never_sent_to_the_extractor(db_session):
    """These are the operator's own mailboxes, so ordinary mail lands in them.
    Spending an AI call on a receipt is waste, and risks inventing a "job"."""
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages",
               return_value=([FetchedMessage(uid=1, sender="billing@aws.amazon.com", body="invoice")], 42)), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email") as mock_extract:
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    mock_extract.assert_not_called()
    assert summary["extracted"] == 0
    assert db_session.query(Job).count() == 0


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

    summary = _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="a")],
        postings=[ExtractedJobPosting(
            title="Backend Engineer", company="Acme", url="https://acme.example/job/1", location="Remote"
        )],
    )

    assert summary["extracted"] == 1
    assert summary["inserted"] == 0


def test_a_single_lane_mailbox_labels_jobs_inference_gave_up_on(db_session):
    mailbox = _seed_mailbox(db_session, lanes=[JobLane.marketing.value])
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="a")],
        postings=[ExtractedJobPosting(title="Zonal Coordinator", company="Acme", url=None, location=None)],
    )
    assert db_session.query(Job).one().lane == JobLane.marketing


def test_the_listing_beats_the_mailbox_label_when_inference_matches(db_session):
    """A marketing alert digest routinely carries one engineering role. The
    job's own title has to win, or that role is filed under the wrong lane."""
    mailbox = _seed_mailbox(db_session, lanes=[JobLane.marketing.value])
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender=LINKEDIN, body="a")],
        postings=[ExtractedJobPosting(title="Senior Software Engineer", company="Acme", url=None, location=None)],
    )
    assert db_session.query(Job).one().lane == JobLane.engineering


def test_an_imap_failure_is_recorded_rather_than_raised(db_session):
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages",
               side_effect=ImapError("Login failed for alerts@jobquickai.site")):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["status"] == "error"
    assert "Login failed" in summary["error"]
    db_session.refresh(mailbox)
    assert "Login failed" in mailbox.last_error


def test_one_broken_mailbox_does_not_stop_the_others(db_session):
    """A revoked password on one market must not silently starve every other
    market's feed."""
    _seed_mailbox(db_session, market="Canada")
    _seed_mailbox(db_session, market="UK")

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages", side_effect=ImapError("down")):
        results = alert_mailboxes.sync_all_mailboxes(db_session)

    assert len(results) == 2
    assert {r["status"] for r in results} == {"error"}


def test_a_recovered_mailbox_clears_its_error(db_session):
    mailbox = _seed_mailbox(db_session)
    mailbox.last_error = "Login failed"
    db_session.commit()

    _sync(db_session, mailbox, messages=[], postings=[])

    db_session.refresh(mailbox)
    assert mailbox.last_error is None


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


# ---------- configuration ----------

def test_adding_a_mailbox_encrypts_the_password(db_session):
    """A plaintext IMAP password in the database is a mailbox anyone with a
    database dump can read."""
    mailbox = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="a@jobquickai.site", market="Canada",
        imap_host="imap.jobquickai.site", imap_username=None, imap_password="s3cret",
    )

    assert mailbox.imap_password_encrypted != "s3cret"
    assert decrypt(mailbox.imap_password_encrypted) == "s3cret"
    assert mailbox.imap_username == "a@jobquickai.site"  # defaults to the address


def test_adding_a_mailbox_without_a_password_is_rejected(db_session):
    import pytest

    with pytest.raises(ValueError):
        alert_mailboxes.upsert_mailbox(
            db_session, admin_id=None, email_address="a@jobquickai.site", market="Canada",
            imap_host="imap.jobquickai.site", imap_username=None, imap_password=None,
        )


def test_resubmitting_an_address_updates_it_instead_of_duplicating(db_session):
    """Re-submitting is how an operator rotates a password or moves hosts. A
    second row would double every job that mailbox reads."""
    alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="a@jobquickai.site", market="Canada",
        imap_host="old.example.com", imap_username=None, imap_password="old",
    )
    updated = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="a@jobquickai.site", market="Canada",
        imap_host="new.example.com", imap_username=None, imap_password="new",
    )

    assert db_session.query(AlertMailbox).count() == 1
    assert updated.imap_host == "new.example.com"
    assert decrypt(updated.imap_password_encrypted) == "new"


def test_an_edit_that_omits_the_password_keeps_the_stored_one(db_session):
    """The API never returns the password, so an edit form cannot round-trip
    it — omitting it must mean "unchanged", not "blank it"."""
    alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="a@jobquickai.site", market="Canada",
        imap_host="imap.jobquickai.site", imap_username=None, imap_password="keepme",
    )
    updated = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="a@jobquickai.site", market="United Kingdom",
        imap_host="imap.jobquickai.site", imap_username=None, imap_password=None,
    )

    assert updated.market == "United Kingdom"
    assert decrypt(updated.imap_password_encrypted) == "keepme"


# ---------- admin API ----------

def test_mailbox_endpoints_require_admin(client):
    data = register_user(client, email="seeker-no-mailboxes@example.com")
    resp = client.get("/api/admin/mailboxes", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 403


def test_the_api_never_returns_the_password(client, db_session):
    """A secret readable back out of the API is a secret one XSS away from
    being someone else's."""
    headers = _make_admin(client)
    _seed_mailbox(db_session, market="Canada")

    body = client.get("/api/admin/mailboxes", headers=headers).text
    assert "app-password" not in body
    assert "password_encrypted" not in body


def test_adding_a_mailbox_over_the_api(client, db_session):
    headers = _make_admin(client, email="add-admin@example.com")

    resp = client.put("/api/admin/mailboxes", headers=headers, json={
        "email_address": "alerts-ca@jobquickai.site",
        "market": "Canada",
        "imap_host": "imap.jobquickai.site",
        "imap_password": "s3cret",
        "lanes": ["marketing"],
    })

    assert resp.status_code == 200
    assert resp.json()["market"] == "Canada"
    assert resp.json()["imap_username"] == "alerts-ca@jobquickai.site"
    assert db_session.query(AlertMailbox).count() == 1


def test_adding_a_mailbox_rejects_a_blank_market(client):
    headers = _make_admin(client, email="blank-market-admin@example.com")
    resp = client.put("/api/admin/mailboxes", headers=headers, json={
        "email_address": "a@jobquickai.site", "market": "   ",
        "imap_host": "imap.jobquickai.site", "imap_password": "x",
    })
    assert resp.status_code == 422


def test_adding_a_mailbox_rejects_an_unknown_lane(client):
    headers = _make_admin(client, email="bad-lane-admin@example.com")
    resp = client.put("/api/admin/mailboxes", headers=headers, json={
        "email_address": "a@jobquickai.site", "market": "Canada",
        "imap_host": "imap.jobquickai.site", "imap_password": "x", "lanes": ["astrology"],
    })
    assert resp.status_code == 422


def test_test_connection_reports_a_failure_without_erroring(client, db_session):
    """A 500 here would tell the operator the app is broken, when what is
    actually broken is the password they just typed."""
    headers = _make_admin(client, email="test-admin@example.com")
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.test_connection",
               side_effect=ImapError("Login failed — use an app password")):
        resp = client.post(f"/api/admin/mailboxes/{mailbox.id}/test", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert "app password" in resp.json()["detail"]


def test_test_connection_reports_success(client, db_session):
    headers = _make_admin(client, email="test-ok-admin@example.com")
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.test_connection"):
        resp = client.post(f"/api/admin/mailboxes/{mailbox.id}/test", headers=headers)

    assert resp.json()["ok"] is True


def test_listing_updating_and_deleting_a_mailbox(client, db_session):
    headers = _make_admin(client, email="crud-admin@example.com")
    mailbox = _seed_mailbox(db_session, market="Canada")

    resp = client.get("/api/admin/mailboxes", headers=headers)
    assert [m["market"] for m in resp.json()] == ["Canada"]

    resp = client.patch(
        f"/api/admin/mailboxes/{mailbox.id}", json={"market": "UK", "is_active": False}, headers=headers
    )
    assert resp.json()["market"] == "UK"
    assert resp.json()["is_active"] is False

    assert client.delete(f"/api/admin/mailboxes/{mailbox.id}", headers=headers).status_code == 204
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

    client.delete(f"/api/admin/mailboxes/{mailbox.id}", headers=headers)

    assert db_session.query(Job).count() == 1


# ---------- diagnosing a mailbox that produces nothing ----------

def test_a_mailbox_that_recognised_no_senders_says_what_it_saw(db_session):
    """The exact shape of "I set it up and nothing happened": mail is arriving,
    but from a board that isn't in the allowlist, or through a forwarder that
    rewrote the From header. Without this it reads as success, 0 inserted."""
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages", return_value=([
        FetchedMessage(uid=1, sender="Bayt <alerts@some-board.example>", body="a"),
        FetchedMessage(uid=2, sender="Bayt <alerts@some-board.example>", body="b"),
        FetchedMessage(uid=3, sender="Forwarder <noreply@forwarder.example>", body="c"),
    ], 42)):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["skipped_senders"] == {"some-board.example": 2, "forwarder.example": 1}

    db_session.refresh(mailbox)
    assert "recognised no job-alert senders" in mailbox.last_error
    assert "some-board.example (2)" in mailbox.last_error
    assert "From header" in mailbox.last_error  # names the forwarding cause too


def test_a_mailbox_that_recognised_something_is_not_flagged(db_session):
    """One stray personal email alongside real alerts is normal, not a fault."""
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages", return_value=([
        FetchedMessage(uid=1, sender=LINKEDIN, body="a"),
        FetchedMessage(uid=2, sender="A Friend <hi@example.com>", body="b"),
    ], 42)), \
         patch("app.services.alert_mailboxes.extract_jobs_from_email", return_value=[]):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["skipped_senders"] == {"example.com": 1}
    db_session.refresh(mailbox)
    assert mailbox.last_error is None


def test_a_quiet_sync_with_no_mail_at_all_is_not_flagged(db_session):
    """Nothing arrived since the last run — the normal case, not a failure."""
    mailbox = _seed_mailbox(db_session)
    _sync(db_session, mailbox, messages=[], postings=[])

    db_session.refresh(mailbox)
    assert mailbox.last_error is None


# ---------- one account, several markets, separate folders ----------

def test_one_account_can_serve_several_markets_through_folders(db_session):
    """Market has to stay a fact inherited from the mailbox — inferring it from
    a free-text location puts Lagos jobs in a Toronto feed. But that needs a
    separate *folder*, not a separate account."""
    canada = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="Canada",
        imap_host="imap.jobquickai.site", imap_username=None, imap_password="pw", imap_folder="Canada",
    )
    uk = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="United Kingdom",
        imap_host="imap.jobquickai.site", imap_username=None, imap_password="pw", imap_folder="UK",
    )

    assert db_session.query(AlertMailbox).count() == 2
    assert canada.id != uk.id
    assert {m.market for m in db_session.query(AlertMailbox).all()} == {"Canada", "United Kingdom"}


def test_each_folder_keeps_its_own_uid_cursor(db_session):
    """A shared cursor across folders would have one market's progress skip
    another market's mail."""
    canada = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="Canada",
        imap_host="h", imap_username=None, imap_password="pw", imap_folder="Canada",
    )
    uk = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="UK",
        imap_host="h", imap_username=None, imap_password="pw", imap_folder="UK",
    )

    _sync(db_session, canada, messages=[FetchedMessage(uid=90, sender=LINKEDIN, body="a")], postings=[])

    db_session.refresh(canada)
    db_session.refresh(uk)
    assert canada.last_seen_uid == 90
    assert uk.last_seen_uid is None


def test_resubmitting_the_same_address_and_folder_still_updates_in_place(db_session):
    alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="Canada",
        imap_host="old.example.com", imap_username=None, imap_password="pw", imap_folder="Canada",
    )
    updated = alert_mailboxes.upsert_mailbox(
        db_session, admin_id=None, email_address="alerts@jobquickai.site", market="Canada",
        imap_host="new.example.com", imap_username=None, imap_password=None, imap_folder="Canada",
    )

    assert db_session.query(AlertMailbox).count() == 1
    assert updated.imap_host == "new.example.com"
    assert decrypt(updated.imap_password_encrypted) == "pw"  # unchanged


# ---------- a failure must always say something ----------

def test_a_timeout_produces_a_message_rather_than_an_empty_string(db_session):
    """A bare socket timeout raises TimeoutError() with no arguments, so
    str(e) is "". The toast read "alerts-canada@jobquickai.site:" and stopped."""
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages",
               side_effect=TimeoutError()):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["status"] == "error"
    assert summary["error"]
    assert "Timed out" in summary["error"]
    assert "imap.jobquickai.site:993" in summary["error"]   # where it was pointed


@pytest.mark.parametrize("failure", [OSError(), ConnectionResetError(), Exception()])
def test_no_failure_can_produce_an_empty_error(db_session, failure):
    """Several connection errors stringify to nothing. None of them may reach
    the UI as a blank message."""
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages", side_effect=failure):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert summary["status"] == "error"
    assert summary["error"] and summary["error"].strip()
    assert type(failure).__name__ in summary["error"] or "Timed out" in summary["error"]


def test_a_failure_that_does_say_something_keeps_its_own_words_plus_the_host(db_session):
    mailbox = _seed_mailbox(db_session)

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages",
               side_effect=ImapError("Login failed for alerts-canada@jobquickai.site")):
        summary = alert_mailboxes.sync_mailbox(db_session, mailbox)

    assert "Login failed" in summary["error"]
    assert "imap.jobquickai.site:993" in summary["error"]


# ---------- what each mailbox has actually produced ----------

def test_the_list_reports_how_many_jobs_each_mailbox_has_ingested(client, db_session):
    """A mailbox can look healthy — connected, synced, no error — and be
    contributing nothing. The page gave no way to tell that apart from one
    doing its job."""
    canada = _seed_mailbox(db_session, market="Canada")
    uk = _seed_mailbox(db_session, market="UK")

    for uid, postings in ((1, 2), (2, 1)):
        _sync(
            db_session, canada,
            messages=[FetchedMessage(uid=uid, sender=LINKEDIN, body="alert")],
            postings=[
                ExtractedJobPosting(title=f"Role {uid}-{n}", company="A",
                                    url=f"https://x.test/{uid}-{n}", location="Toronto, ON")
                for n in range(postings)
            ],
        )

    headers = _make_admin(client, email="counts-admin@example.com")
    rows = {m["market"]: m for m in client.get("/api/admin/mailboxes", headers=headers).json()}

    assert rows["Canada"]["jobs_ingested"] == 3      # 2 + 1 across two runs
    assert rows["Canada"]["last_run_fetched"] == 1
    assert rows["Canada"]["last_run_inserted"] == 1  # the most recent run only
    assert rows["UK"]["jobs_ingested"] == 0
    assert rows["UK"]["last_run_fetched"] == 0


def test_a_mailbox_reading_mail_but_adding_nothing_is_visible_as_such(client, db_session):
    """The gap between fetched and inserted is the diagnosis: mail is
    arriving and none of it is becoming supply."""
    mailbox = _seed_mailbox(db_session, market="Canada")
    _sync(
        db_session, mailbox,
        messages=[FetchedMessage(uid=1, sender="Random <news@substack.com>", body="not an alert")],
        postings=[],
    )

    headers = _make_admin(client, email="gap-admin@example.com")
    row = client.get("/api/admin/mailboxes", headers=headers).json()[0]

    assert row["last_run_fetched"] == 1
    assert row["last_run_inserted"] == 0
    assert row["jobs_ingested"] == 0


def test_counting_does_not_issue_a_query_per_mailbox(db_session):
    """Five mailboxes on one page is ten round trips done the naive way."""
    from sqlalchemy import event
    from app.db.base import engine

    for market in ("Canada", "UK", "USA", "Nigeria", "UAE"):
        _seed_mailbox(db_session, market=market)
    mailboxes = db_session.query(AlertMailbox).all()

    statements = []
    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        alert_mailboxes.with_counts(db_session, mailboxes)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len(statements) == 2, statements


def test_counting_nothing_does_not_query_at_all(db_session):
    assert alert_mailboxes.with_counts(db_session, []) == []


def test_a_failed_run_is_not_reported_as_having_found_no_mail(client, db_session):
    """A run that timed out fetched nothing because it never connected, not
    because nothing was waiting. Both have fetched_count 0, so the status has
    to come through or the UI states something it cannot support."""
    mailbox = _seed_mailbox(db_session, market="USA")

    with patch("app.services.alert_mailboxes.imap_client.fetch_messages", side_effect=TimeoutError()):
        alert_mailboxes.sync_mailbox(db_session, mailbox)

    headers = _make_admin(client, email="failed-run-admin@example.com")
    row = client.get("/api/admin/mailboxes", headers=headers).json()[0]

    assert row["last_run_status"] == "error"
    assert row["last_run_fetched"] == 0


def test_a_successful_run_that_found_nothing_is_marked_successful(client, db_session):
    mailbox = _seed_mailbox(db_session, market="Nigeria")
    _sync(db_session, mailbox, messages=[], postings=[])

    headers = _make_admin(client, email="empty-run-admin@example.com")
    row = client.get("/api/admin/mailboxes", headers=headers).json()[0]

    assert row["last_run_status"] == "success"
    assert row["last_run_fetched"] == 0
