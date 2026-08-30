from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.crypto import encrypt
from app.models.email_sync_run import EmailSyncRun
from app.models.gmail_connection import GmailConnection
from app.models.job import Job
from app.schemas.ai import ExtractedJobPosting
from app.services import email_bridge
from tests.conftest import auth_headers, register_user


def _seed_connection(session, user_id, expires_in_minutes=60) -> GmailConnection:
    connection = GmailConnection(
        user_id=user_id,
        access_token_encrypted=encrypt("fake-access-token"),
        refresh_token_encrypted=encrypt("fake-refresh-token"),
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        label_id="Label_1",
    )
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


def test_sync_user_extracts_and_inserts_jobs(db_session):
    from app.db.base import SessionLocal
    from app.models.user import User

    user = User(email="sync@example.com", password_hash="x", full_name="Sync User", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    connection = _seed_connection(db_session, user.id)
    db_session.commit()

    fake_message = {
        "payload": {
            "headers": [{"name": "From", "value": "LinkedIn <jobalerts-noreply@linkedin.com>"}],
            "mimeType": "text/plain",
            "body": {"data": "ZmFrZSBib2R5IHRleHQ="},  # "fake body text"
        }
    }
    fake_postings = [ExtractedJobPosting(title="Backend Engineer", company="Acme", url=None, location="Remote")]

    with patch("app.services.email_bridge.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.email_bridge.gmail_oauth.get_message", return_value=fake_message), \
         patch("app.services.email_bridge.extract_jobs_from_email", return_value=fake_postings):
        summary = email_bridge.sync_user(db_session, user)

    assert summary["status"] == "success"
    assert summary["fetched"] == 1
    assert summary["extracted"] == 1
    assert summary["inserted"] == 1

    job = db_session.query(Job).filter(Job.source == "email-linkedin").first()
    assert job is not None
    assert job.title == "Backend Engineer"
    assert "linkedin.com/jobs/search" in job.source_url  # no url in posting -> fallback used

    run = db_session.query(EmailSyncRun).filter(EmailSyncRun.user_id == user.id).first()
    assert run.status == "success"
    assert run.inserted_count == 1


def test_sync_user_skips_duplicate_urls(db_session):
    from app.models.user import User

    user = User(email="dupe-sync@example.com", password_hash="x", full_name="Sync User", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    _seed_connection(db_session, user.id)
    db_session.add(Job(
        title="Backend Engineer", description="desc", requirements=[], location="Remote",
        job_type="full_time", experience_level="mid", source="remotive",
        source_url="https://acme.example/job/1",
    ))
    db_session.commit()

    fake_message = {
        "payload": {
            "headers": [{"name": "From", "value": "LinkedIn <jobalerts-noreply@linkedin.com>"}],
            "mimeType": "text/plain",
            "body": {"data": "Zm9v"},
        }
    }
    fake_postings = [ExtractedJobPosting(title="Backend Engineer", company="Acme", url="https://acme.example/job/1", location="Remote")]

    with patch("app.services.email_bridge.gmail_oauth.list_message_ids", return_value=["m1"]), \
         patch("app.services.email_bridge.gmail_oauth.get_message", return_value=fake_message), \
         patch("app.services.email_bridge.extract_jobs_from_email", return_value=fake_postings):
        summary = email_bridge.sync_user(db_session, user)

    assert summary["extracted"] == 1
    assert summary["inserted"] == 0  # already existed from another source


def test_sync_user_records_error_without_raising(db_session):
    from app.models.user import User

    user = User(email="broken-sync@example.com", password_hash="x", full_name="Sync User", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    _seed_connection(db_session, user.id)
    db_session.commit()

    with patch("app.services.email_bridge.gmail_oauth.list_message_ids", side_effect=RuntimeError("Gmail API down")):
        summary = email_bridge.sync_user(db_session, user)

    assert summary["status"] == "error"
    assert "Gmail API down" in summary["error"]

    run = db_session.query(EmailSyncRun).filter(EmailSyncRun.user_id == user.id).first()
    assert run.status == "error"


def test_sync_user_refreshes_expired_token(db_session):
    from app.models.user import User

    user = User(email="expired-sync@example.com", password_hash="x", full_name="Sync User", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    connection = _seed_connection(db_session, user.id, expires_in_minutes=-5)  # already expired
    db_session.commit()

    with patch("app.services.email_bridge.gmail_oauth.refresh_access_token", return_value={"access_token": "new-token", "expires_in": 3600}) as mock_refresh, \
         patch("app.services.email_bridge.gmail_oauth.list_message_ids", return_value=[]) as mock_list:
        email_bridge.sync_user(db_session, user)

    mock_refresh.assert_called_once()
    mock_list.assert_called_once_with("new-token", "Label_1", email_bridge.settings.EMAIL_SYNC_QUERY_WINDOW)


def test_sync_user_raises_value_error_when_not_connected(db_session):
    from app.models.user import User
    import pytest

    user = User(email="noconn@example.com", password_hash="x", full_name="X", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    db_session.commit()

    with pytest.raises(ValueError):
        email_bridge.sync_user(db_session, user)


# ---------- integration router tests ----------

def test_connect_endpoint_returns_authorization_url(client):
    data = register_user(client, email="connect@example.com")
    resp = client.get("/api/integrations/gmail/connect", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 200
    assert "accounts.google.com" in resp.json()["authorization_url"]


def test_status_endpoint_reports_not_connected_by_default(client):
    data = register_user(client, email="status@example.com")
    resp = client.get("/api/integrations/gmail/status", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "last_synced_at": None}


def test_callback_rejects_missing_code(client):
    resp = client.get("/api/integrations/gmail/callback", params={"state": "whatever"})
    assert resp.status_code == 400


def test_callback_rejects_invalid_state(client):
    resp = client.get("/api/integrations/gmail/callback", params={"code": "abc", "state": "not-a-real-token"})
    assert resp.status_code == 400


@patch("app.routers.integrations.email_bridge.handle_oauth_callback")
def test_callback_connects_gmail_for_the_right_user(mock_handle, client):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    data = register_user(client, email="callback@example.com")
    mock_handle.return_value = SimpleNamespace(connected_at=datetime.now(timezone.utc))

    connect_resp = client.get("/api/integrations/gmail/connect", headers=auth_headers(data["access_token"]))
    auth_url = connect_resp.json()["authorization_url"]
    from urllib.parse import urlparse, parse_qs
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    resp = client.get("/api/integrations/gmail/callback", params={"code": "google-code", "state": state})
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    mock_handle.assert_called_once()
    called_user = mock_handle.call_args[0][1]
    assert called_user.email == "callback@example.com"


def test_disconnect_and_manual_sync_require_connection(client):
    data = register_user(client, email="nogmail@example.com")
    headers = auth_headers(data["access_token"])

    resp = client.post("/api/integrations/gmail/sync", headers=headers)
    assert resp.status_code == 404

    resp = client.delete("/api/integrations/gmail", headers=headers)
    assert resp.status_code == 204  # disconnecting when nothing's connected is a no-op, not an error
