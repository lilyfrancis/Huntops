"""The IMAP fetch layer — new code, and the one place a mistake means either
paying twice for the same AI call or silently skipping real mail."""

import email
import imaplib
from email.message import EmailMessage
from unittest.mock import patch

import pytest

from app.services import imap_client
from app.services.imap_client import Credentials, ImapError

CREDS = Credentials(
    host="imap.example.com", port=993, username="alerts@huntops.site",
    password="app-password", use_ssl=True, folder="INBOX",
)


def _raw(*, sender="LinkedIn <jobalerts-noreply@linkedin.com>", plain=None, html=None, subject="Jobs") -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = subject
    if plain is not None and html is not None:
        msg.set_content(plain)
        msg.add_alternative(html, subtype="html")
    elif html is not None:
        msg.set_content(html, subtype="html")
    else:
        msg.set_content(plain or "")
    return msg.as_bytes()


class FakeIMAP:
    """Enough of imaplib.IMAP4 to drive fetch_messages."""

    def __init__(self, *, messages: dict[int, bytes], uidvalidity: int = 42, select_ok: bool = True):
        self.messages = messages
        self.uidvalidity = uidvalidity
        self.select_ok = select_ok
        self.searches: list[tuple] = []
        self.fetched: list[int] = []
        self.logged_out = False

    def login(self, username, password):
        return ("OK", [b"logged in"])

    def select(self, folder, readonly=False):
        return ("OK", [b"1"]) if self.select_ok else ("NO", [b"no such folder"])

    def response(self, key):
        return (key, [str(self.uidvalidity).encode()])

    def uid(self, command, *args):
        if command == "SEARCH":
            self.searches.append(args)
            return ("OK", [b" ".join(str(u).encode() for u in sorted(self.messages))])
        if command == "FETCH":
            uid = int(args[0])
            self.fetched.append(uid)
            return ("OK", [(b"1 (RFC822 {n}", self.messages[uid])])
        raise AssertionError(f"unexpected UID command {command}")

    def logout(self):
        self.logged_out = True
        return ("BYE", [b"bye"])


def _run(fake, **kwargs):
    defaults = {"since_uid": None, "uid_validity": None, "lookback_days": 3}
    with patch("app.services.imap_client.imaplib.IMAP4_SSL", return_value=fake):
        return imap_client.fetch_messages(CREDS, **{**defaults, **kwargs})


# ---------- body extraction ----------

def test_plain_text_is_preferred_over_html():
    """Same content, far fewer tokens to send to the extractor."""
    msg = email.message_from_bytes(_raw(plain="Backend Engineer at Acme", html="<p>Backend Engineer</p>"))
    _, body = imap_client.extract_sender_and_body(msg)
    assert body.strip() == "Backend Engineer at Acme"


def test_html_is_used_when_there_is_no_plain_part():
    msg = email.message_from_bytes(_raw(html="<p>Backend Engineer</p>"))
    _, body = imap_client.extract_sender_and_body(msg)
    assert "Backend Engineer" in body


def test_encoded_sender_headers_are_decoded():
    """From headers arrive RFC 2047-encoded more often than not, and the
    provider is matched on that string."""
    msg = email.message_from_bytes(_raw(sender="=?utf-8?B?TGlua2VkSW4=?= <jobalerts-noreply@linkedin.com>"))
    sender, _ = imap_client.extract_sender_and_body(msg)
    assert "LinkedIn" in sender


def test_attachments_are_not_treated_as_body_text():
    msg = EmailMessage()
    msg["From"] = "x@linkedin.com"
    msg.set_content("Real alert text")
    msg.add_attachment(b"%PDF-1.4 not job text", maintype="application", subtype="pdf", filename="a.pdf")

    _, body = imap_client.extract_sender_and_body(email.message_from_bytes(msg.as_bytes()))
    assert "Real alert text" in body
    assert "PDF" not in body


# ---------- incremental fetching ----------

def test_first_sync_searches_by_date():
    fake = FakeIMAP(messages={5: _raw(plain="a")})
    messages, validity = _run(fake)

    assert fake.searches[0][1] == "SINCE"
    assert validity == 42
    assert [m.uid for m in messages] == [5]


def test_a_later_sync_resumes_from_the_last_uid():
    """Extraction costs an AI call per message. Re-reading yesterday's mail
    every morning is paying repeatedly for an answer already known."""
    fake = FakeIMAP(messages={9: _raw(plain="a")})
    _run(fake, since_uid=8, uid_validity=42)

    assert fake.searches[0] == (None, "UID", "9:*")


def test_the_newest_message_is_not_reprocessed_when_nothing_is_newer():
    """"UID n:*" always returns at least the newest message even when nothing
    is newer than n — taking that at face value re-extracts it every run."""
    fake = FakeIMAP(messages={8: _raw(plain="a")})
    messages, _ = _run(fake, since_uid=8, uid_validity=42)

    assert messages == []
    assert fake.fetched == []


def test_a_changed_uidvalidity_falls_back_to_a_date_window():
    """A server that renumbers a folder makes every stored UID mean something
    else. Resuming from one would silently skip real mail."""
    fake = FakeIMAP(messages={2: _raw(plain="a")}, uidvalidity=99)
    messages, validity = _run(fake, since_uid=500, uid_validity=42)

    assert fake.searches[0][1] == "SINCE"
    assert validity == 99
    assert [m.uid for m in messages] == [2]


def test_a_long_neglected_mailbox_is_capped_at_the_newest_messages():
    """A mailbox unsynced for months must not extract — and pay for — ten
    thousand messages in one run, and if it can only take some, the recent
    ones are the ones worth having."""
    fake = FakeIMAP(messages={uid: _raw(plain=f"job {uid}") for uid in range(1, 501)})
    messages, _ = _run(fake)

    assert len(messages) == imap_client.MAX_MESSAGES_PER_SYNC
    assert max(m.uid for m in messages) == 500
    assert min(m.uid for m in messages) == 501 - imap_client.MAX_MESSAGES_PER_SYNC


# ---------- failure reporting ----------

def test_a_bad_password_says_to_use_an_app_password():
    """The commonest cause by far, and "AUTHENTICATIONFAILED" alone helps nobody."""
    fake = FakeIMAP(messages={})
    fake.login = lambda u, p: (_ for _ in ()).throw(imaplib.IMAP4.error("AUTHENTICATIONFAILED"))

    with patch("app.services.imap_client.imaplib.IMAP4_SSL", return_value=fake):
        with pytest.raises(ImapError, match="app password"):
            imap_client.test_connection(CREDS)


def test_an_unreachable_host_is_reported_with_the_address_tried():
    with patch("app.services.imap_client.imaplib.IMAP4_SSL", side_effect=OSError("Name or service not known")):
        with pytest.raises(ImapError, match="imap.example.com:993"):
            imap_client.test_connection(CREDS)


def test_a_missing_folder_names_the_folder():
    fake = FakeIMAP(messages={}, select_ok=False)
    with patch("app.services.imap_client.imaplib.IMAP4_SSL", return_value=fake):
        with pytest.raises(ImapError, match="INBOX"):
            imap_client.test_connection(CREDS)


def test_the_connection_is_closed_even_when_the_folder_is_missing():
    """A leaked IMAP session holds a server-side slot; most hosts allow very
    few concurrently, so leaking one per failed sync locks the mailbox out."""
    fake = FakeIMAP(messages={}, select_ok=False)
    with patch("app.services.imap_client.imaplib.IMAP4_SSL", return_value=fake):
        with pytest.raises(ImapError):
            imap_client.test_connection(CREDS)
    assert fake.logged_out is True
