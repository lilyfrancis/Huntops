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
    url = gmail_oauth.build_authorization_url(state="abc123")
    assert "client_id=" in url
    assert "state=abc123" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "gmail.readonly" in url


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
