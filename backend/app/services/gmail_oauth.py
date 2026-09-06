"""Sending mail as a user, over Gmail's API.

All that remains of the Gmail integration. Reading job alerts moved to IMAP
against the operator's own mailboxes, which needs no OAuth client, no consent
screen and no Google review; what is left is the one thing that genuinely
requires a user's own grant — sending outreach from their address.

Thin httpx rather than the Google SDK, consistent with how every other
outbound integration here talks to its API directly.
"""

import base64
import urllib.parse
from email.mime.text import MIMEText

import httpx

from app.core.config import get_settings

settings = get_settings()

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
HTTP_TIMEOUT = 15.0

# The only Gmail scope this product asks anyone for. Alert mailboxes are read
# over IMAP, so nothing here needs a *restricted* scope, and gmail.send alone
# is merely sensitive — a materially smaller thing to put in front of Google.
SEND_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailAPIError(Exception):
    pass


def build_authorization_url(state: str, scopes: list[str]) -> str:
    """`scopes` is required, not defaulted: a default here is how the send-only
    flow would silently start asking for inbox read access again."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",  # forces a refresh_token even on repeat consent
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Token exchange failed: {resp.text[:500]}")
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Token refresh failed: {resp.text[:500]}")
    return resp.json()


def revoke_token(token: str) -> None:
    try:
        httpx.post(REVOKE_URL, params={"token": token}, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError:
        pass  # best-effort — a failed revoke shouldn't block disconnecting locally


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def send_message(access_token: str, to: str, subject: str, body_text: str) -> str:
    """Send a plain-text email from the connected user's own Gmail account.
    Returns the sent message's id."""
    mime_message = MIMEText(body_text)
    mime_message["To"] = to
    mime_message["Subject"] = subject
    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode()

    resp = httpx.post(
        f"{GMAIL_API_BASE}/messages/send",
        headers=_auth_headers(access_token),
        json={"raw": raw},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Sending message failed: {resp.text[:500]}")
    return resp.json()["id"]


