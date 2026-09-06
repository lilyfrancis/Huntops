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


def test_connecting_your_own_gmail_never_asks_to_read_it():
    """The integrations page promises "we never read your mail". This is the
    line that has to be true for that promise to hold — and since alert
    mailboxes moved to IMAP, send is the only Gmail scope left anywhere."""
    from app.models.user import User
    from app.services import email_bridge

    user = User(id=uuid.uuid4(), email="x@example.com", password_hash="x", full_name="X", role="job_seeker")
    url = email_bridge.get_connect_url(user)

    assert "gmail.send" in url
    assert "gmail.readonly" not in url
    assert "gmail.labels" not in url
    assert "gmail.settings" not in url


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
