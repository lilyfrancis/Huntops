"""Thin Gmail/OAuth2 client over httpx — no heavy Google SDK dependency,
consistent with how the aggregation service talks to job-board APIs directly.
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

# Two flows, two very different asks — kept apart on purpose.
#
# An operator's alert mailbox has to be read, labelled and filtered. A job
# seeker connecting their own account is only ever sent *from*; asking them for
# read access to their entire inbox to do that is over-asking, and the UI
# already (correctly) promises we don't. It also matters for Google review:
# gmail.readonly is a *restricted* scope needing a security assessment, while
# gmail.send alone is merely sensitive.
MAILBOX_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    # Optional. Only used to create the routing filters automatically, and it
    # is a *restricted* scope — dropping it is one fewer thing to justify to
    # Google, at the cost of the operator creating the filter by hand once per
    # mailbox. Connecting without it works; the mailbox just says so.
    "https://www.googleapis.com/auth/gmail.settings.basic",
]

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


def get_profile_email(access_token: str) -> str:
    """The address of the mailbox this grant belongs to.

    Asked of Gmail rather than typed in by the admin: a typo would silently
    attach a market's whole feed to the wrong inbox, and there is no later
    point at which that mistake becomes visible.
    """
    resp = httpx.get(f"{GMAIL_API_BASE}/profile", headers=_auth_headers(access_token), timeout=HTTP_TIMEOUT)
    if resp.status_code >= 400:
        raise GmailAPIError(f"Reading mailbox profile failed: {resp.text[:500]}")
    address = resp.json().get("emailAddress")
    if not address:
        raise GmailAPIError("Gmail returned no email address for this account")
    return address


def ensure_label(access_token: str, name: str) -> str:
    """Return the Gmail-assigned id for `name`, creating it if it doesn't exist."""
    resp = httpx.get(f"{GMAIL_API_BASE}/labels", headers=_auth_headers(access_token), timeout=HTTP_TIMEOUT)
    if resp.status_code >= 400:
        raise GmailAPIError(f"Listing labels failed: {resp.text[:500]}")

    for label in resp.json().get("labels", []):
        if label.get("name") == name:
            return label["id"]

    resp = httpx.post(
        f"{GMAIL_API_BASE}/labels",
        headers=_auth_headers(access_token),
        json={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Creating label failed: {resp.text[:500]}")
    return resp.json()["id"]


def ensure_filter(access_token: str, domain: str, label_id: str) -> bool:
    """Route mail from `domain` into `label_id`. True if the filter now exists.

    Returns rather than raises because a filter we couldn't create is a
    degraded mailbox, not a failed connection — the caller decides what to say
    about it. It has to *report* the failure though: this previously only
    caught transport errors, so a 403 from a missing settings scope came back
    as an ordinary response and was discarded, leaving a mailbox that silently
    ingested nothing with no indication why.
    """
    try:
        resp = httpx.post(
            f"{GMAIL_API_BASE}/settings/filters",
            headers=_auth_headers(access_token),
            json={"criteria": {"from": domain}, "action": {"addLabelIds": [label_id]}},
            timeout=HTTP_TIMEOUT,
        )
    except httpx.HTTPError:
        return False

    if resp.status_code < 400:
        return True
    # An identical filter already being there is the state we wanted.
    if resp.status_code == 409 or "already exist" in resp.text.lower():
        return True
    return False


def list_message_ids(access_token: str, label_id: str, query: str) -> list[str]:
    resp = httpx.get(
        f"{GMAIL_API_BASE}/messages",
        headers=_auth_headers(access_token),
        params={"labelIds": label_id, "q": query, "maxResults": 50},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Listing messages failed: {resp.text[:500]}")
    return [m["id"] for m in resp.json().get("messages", [])]


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


def get_message(access_token: str, message_id: str) -> dict:
    resp = httpx.get(
        f"{GMAIL_API_BASE}/messages/{message_id}",
        headers=_auth_headers(access_token),
        params={"format": "full"},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise GmailAPIError(f"Fetching message {message_id} failed: {resp.text[:500]}")
    return resp.json()
