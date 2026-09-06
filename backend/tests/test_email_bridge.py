"""The user's own Gmail grant — now only ever used to send outreach as them.

Mining a user's inbox for job alerts moved to the admin-owned central
mailboxes (see test_alert_mailboxes.py), so the sync tests that used to live
here went with it.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.core.crypto import encrypt
from app.models.gmail_connection import GmailConnection
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


# ---------- integration router tests ----------

def test_connect_is_refused_when_the_feature_is_off(client):
    """Default state. The OAuth client is an Internal Workspace app, so Google
    blocks consent for anyone outside the Workspace — starting the flow would
    only hand a job seeker an access-denied screen with no explanation."""
    data = register_user(client, email="connect-off@example.com")
    resp = client.get("/api/integrations/gmail/connect", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 404
    assert "reply-to" in resp.json()["detail"]


def test_connect_returns_an_authorization_url_when_enabled(client, monkeypatch):
    from app.routers import integrations

    monkeypatch.setattr(integrations.settings, "ENABLE_USER_GMAIL_CONNECT", True)
    data = register_user(client, email="connect@example.com")
    resp = client.get("/api/integrations/gmail/connect", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 200
    assert "accounts.google.com" in resp.json()["authorization_url"]


def test_status_endpoint_reports_not_connected_by_default(client):
    data = register_user(client, email="status@example.com")
    resp = client.get("/api/integrations/gmail/status", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 200
    assert resp.json() == {"available": False, "connected": False, "connected_at": None}


def test_status_still_reports_a_connection_made_before_the_feature_was_switched_off(client, db_session):
    """Someone who connected earlier keeps control of it — the feature going
    away must not strand a live grant with no way to revoke it."""
    from app.models.user import User

    data = register_user(client, email="legacy-connection@example.com")
    user = db_session.query(User).filter(User.email == "legacy-connection@example.com").one()
    _seed_connection(db_session, user.id)

    body = client.get("/api/integrations/gmail/status", headers=auth_headers(data["access_token"])).json()
    assert body["available"] is False
    assert body["connected"] is True


def _redirect_query(resp) -> dict:
    from urllib.parse import parse_qs, urlparse

    location = resp.headers["location"]
    return parse_qs(urlparse(location).query)


def test_callback_rejects_missing_code(client):
    resp = client.get("/api/integrations/gmail/callback", params={"state": "whatever"}, follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert _redirect_query(resp)["gmail"] == ["error"]


def test_callback_rejects_invalid_state(client):
    resp = client.get(
        "/api/integrations/gmail/callback", params={"code": "abc", "state": "not-a-real-token"}, follow_redirects=False
    )
    assert resp.status_code in (302, 307)
    assert _redirect_query(resp)["gmail"] == ["error"]


@patch("app.routers.integrations.email_bridge.handle_oauth_callback")
def test_callback_connects_gmail_for_the_right_user(mock_handle, client, monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.routers import integrations

    monkeypatch.setattr(integrations.settings, "ENABLE_USER_GMAIL_CONNECT", True)
    data = register_user(client, email="callback@example.com")
    mock_handle.return_value = SimpleNamespace(connected_at=datetime.now(timezone.utc))

    connect_resp = client.get("/api/integrations/gmail/connect", headers=auth_headers(data["access_token"]))
    auth_url = connect_resp.json()["authorization_url"]
    from urllib.parse import urlparse, parse_qs
    state = parse_qs(urlparse(auth_url).query)["state"][0]

    resp = client.get(
        "/api/integrations/gmail/callback", params={"code": "google-code", "state": state}, follow_redirects=False
    )
    assert resp.status_code in (302, 307)
    assert _redirect_query(resp)["gmail"] == ["connected"]
    mock_handle.assert_called_once()
    called_user = mock_handle.call_args[0][1]
    assert called_user.email == "callback@example.com"


def test_disconnect_is_a_noop_when_nothing_is_connected(client):
    data = register_user(client, email="nogmail@example.com")
    resp = client.delete("/api/integrations/gmail", headers=auth_headers(data["access_token"]))
    assert resp.status_code == 204


def test_token_refresh_reuses_a_still_valid_token(db_session):
    """A grant that is not near expiry must not burn a refresh call — that is
    a network round trip per sync, per mailbox, for nothing."""
    from app.models.user import User
    from app.services.gmail_tokens import get_valid_access_token

    user = User(email="fresh-token@example.com", password_hash="x", full_name="X", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    connection = _seed_connection(db_session, user.id, expires_in_minutes=60)

    with patch("app.services.gmail_tokens.gmail_oauth.refresh_access_token") as mock_refresh:
        token = get_valid_access_token(db_session, connection)

    mock_refresh.assert_not_called()
    assert token == "fake-access-token"


def test_token_refresh_replaces_an_expired_token(db_session):
    from app.models.user import User
    from app.services.gmail_tokens import get_valid_access_token

    user = User(email="stale-token@example.com", password_hash="x", full_name="X", role="job_seeker")
    db_session.add(user)
    db_session.flush()
    connection = _seed_connection(db_session, user.id, expires_in_minutes=-5)

    with patch(
        "app.services.gmail_tokens.gmail_oauth.refresh_access_token",
        return_value={"access_token": "new-token", "expires_in": 3600},
    ) as mock_refresh:
        token = get_valid_access_token(db_session, connection)

    mock_refresh.assert_called_once()
    assert token == "new-token"
