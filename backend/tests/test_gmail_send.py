import base64
from unittest.mock import MagicMock, patch

import pytest

from app.services import gmail_oauth


@patch("app.services.gmail_oauth.httpx.post")
def test_send_message_builds_valid_mime_and_posts(mock_post):
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {"id": "sent-msg-1"})

    message_id = gmail_oauth.send_message("token", "jane@acme.com", "Subject line", "Body text here")

    assert message_id == "sent-msg-1"
    call_kwargs = mock_post.call_args.kwargs
    raw = call_kwargs["json"]["raw"]
    decoded = base64.urlsafe_b64decode(raw).decode()
    assert "To: jane@acme.com" in decoded
    assert "Subject: Subject line" in decoded
    assert "Body text here" in decoded


@patch("app.services.gmail_oauth.httpx.post")
def test_send_message_raises_on_error(mock_post):
    mock_post.return_value = MagicMock(status_code=403, text="insufficient scope")
    with pytest.raises(gmail_oauth.GmailAPIError):
        gmail_oauth.send_message("token", "jane@acme.com", "Subject", "Body")
