import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.crypto import decrypt, encrypt
from app.services import gmail_oauth


def test_encrypt_decrypt_roundtrip():
    secret = "1//gmail-refresh-token-example"
    encrypted = encrypt(secret)
    assert encrypted != secret
    assert decrypt(encrypted) == secret


def test_build_authorization_url_includes_required_params():
    url = gmail_oauth.build_authorization_url(state="abc123", scopes=gmail_oauth.MAILBOX_SCOPES)
    assert "client_id=" in url
    assert "state=abc123" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "gmail.readonly" in url


def test_connecting_your_own_gmail_never_asks_to_read_it():
    """The integrations page promises "we never read your mail". This is the
    line that has to be true for that promise to hold."""
    from app.models.user import User
    from app.services import email_bridge

    user = User(id=uuid.uuid4(), email="x@example.com", password_hash="x", full_name="X", role="job_seeker")
    url = email_bridge.get_connect_url(user)

    assert "gmail.send" in url
    assert "gmail.readonly" not in url
    assert "gmail.labels" not in url
    assert "gmail.settings" not in url


def test_an_alert_mailbox_asks_for_read_and_filter_access_but_not_send():
    """Operator mailboxes are read, laballed and filtered — never sent from.
    Send belongs to the user's own grant."""
    from app.models.user import User
    from app.services import alert_mailboxes

    admin = User(id=uuid.uuid4(), email="a@example.com", password_hash="x", full_name="A", role="admin")
    url = alert_mailboxes.get_connect_url(admin, market="Canada", label=None, lanes=[])

    assert "gmail.readonly" in url
    assert "gmail.labels" in url
    assert "gmail.send" not in url


@patch("app.services.gmail_oauth.httpx.post")
def test_exchange_code_for_tokens_success(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "a", "refresh_token": "r", "expires_in": 3600})
    result = gmail_oauth.exchange_code_for_tokens("some-code")
    assert result["access_token"] == "a"


@patch("app.services.gmail_oauth.httpx.post")
def test_exchange_code_for_tokens_raises_on_error(mock_post):
    mock_post.return_value = MagicMock(status_code=400, text="invalid_grant")
    with pytest.raises(gmail_oauth.GmailAPIError):
        gmail_oauth.exchange_code_for_tokens("bad-code")


@patch("app.services.gmail_oauth.httpx.get")
@patch("app.services.gmail_oauth.httpx.post")
def test_ensure_label_creates_when_missing(mock_post, mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"labels": [{"id": "Label_1", "name": "Other"}]})
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "Label_99"})

    label_id = gmail_oauth.ensure_label("token", "HuntOps")
    assert label_id == "Label_99"
    mock_post.assert_called_once()


@patch("app.services.gmail_oauth.httpx.get")
def test_ensure_label_returns_existing_without_creating(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"labels": [{"id": "Label_5", "name": "HuntOps"}]})
    with patch("app.services.gmail_oauth.httpx.post") as mock_post:
        label_id = gmail_oauth.ensure_label("token", "HuntOps")
    assert label_id == "Label_5"
    mock_post.assert_not_called()


@patch("app.services.gmail_oauth.httpx.get")
def test_list_message_ids(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"messages": [{"id": "m1"}, {"id": "m2"}]})
    ids = gmail_oauth.list_message_ids("token", "Label_1", "newer_than:2d")
    assert ids == ["m1", "m2"]


# ---------- filter creation has to report failure, not swallow it ----------

@patch("app.services.gmail_oauth.httpx.post")
def test_ensure_filter_reports_a_permission_failure(mock_post):
    """A 403 from a missing settings scope comes back as an ordinary response,
    not an exception. Discarding it leaves a mailbox that ingests nothing with
    no indication why."""
    mock_post.return_value = MagicMock(status_code=403, text='{"error": "insufficient scope"}')
    assert gmail_oauth.ensure_filter("token", "linkedin.com", "Label_1") is False


@patch("app.services.gmail_oauth.httpx.post")
def test_ensure_filter_treats_an_existing_filter_as_success(mock_post):
    mock_post.return_value = MagicMock(status_code=409, text="Filter already exists")
    assert gmail_oauth.ensure_filter("token", "linkedin.com", "Label_1") is True


@patch("app.services.gmail_oauth.httpx.post")
def test_ensure_filter_succeeds_on_creation(mock_post):
    mock_post.return_value = MagicMock(status_code=200, text="{}")
    assert gmail_oauth.ensure_filter("token", "linkedin.com", "Label_1") is True
