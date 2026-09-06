"""Reading job-alert email over IMAP.

This replaces the Gmail API. The mailboxes are the operator's own, and IMAP
needs no OAuth client, no consent screen, no scopes and no Google review — a
category of problem that simply stops existing. It also frees the mailboxes
from Google entirely: any provider that speaks IMAP will do.

Sync is incremental by UID rather than by date. Extraction is the expensive
part of ingestion (one AI call per message), so re-reading yesterday's mail
every morning would be paying repeatedly for an answer already known.
"""

import email
import imaplib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message

logger = logging.getLogger(__name__)

# IMAP servers are slower to answer than an HTTP API, and a hung socket here
# would stall the whole scheduled run.
IMAP_TIMEOUT = 30.0

# Ceiling on one sync. A mailbox left unsynced for months must not try to
# extract ten thousand messages — and pay for each — in a single run.
MAX_MESSAGES_PER_SYNC = 200


class ImapError(Exception):
    pass


@dataclass
class FetchedMessage:
    uid: int
    sender: str
    body: str


@dataclass
class Credentials:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool
    folder: str


def _decode(value: str | None) -> str:
    """Header values arrive RFC 2047-encoded (=?utf-8?B?...?=) more often than not."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="ignore")
    except LookupError:
        # A charset the runtime doesn't know is common in bulk mail; the bytes
        # are usually still mostly ASCII, so this recovers the useful part
        # rather than discarding the message.
        return payload.decode("utf-8", errors="ignore")


def extract_sender_and_body(msg: Message) -> tuple[str, str]:
    """Returns (From header, best-effort body text).

    Prefers text/plain over text/html: the plain part of a job-alert email is
    the same content with none of the markup, which means fewer tokens to send
    to the extractor for exactly the same result.
    """
    sender = _decode(msg.get("From"))

    if not msg.is_multipart():
        return sender, _part_text(msg)

    plain, html = "", ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        # Skip attachments — a PDF's bytes are not the alert text.
        if "attachment" in (part.get("Content-Disposition") or "").lower():
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain" and not plain:
            plain = _part_text(part)
        elif content_type == "text/html" and not html:
            html = _part_text(part)

    return sender, plain or html


def _connect(creds: Credentials) -> imaplib.IMAP4:
    try:
        if creds.use_ssl:
            conn: imaplib.IMAP4 = imaplib.IMAP4_SSL(creds.host, creds.port, timeout=IMAP_TIMEOUT)
        else:
            conn = imaplib.IMAP4(creds.host, creds.port, timeout=IMAP_TIMEOUT)
            conn.starttls()
    except (imaplib.IMAP4.error, OSError) as e:
        raise ImapError(f"Could not connect to {creds.host}:{creds.port} — {e}")

    try:
        conn.login(creds.username, creds.password)
    except imaplib.IMAP4.error as e:
        conn.logout()
        # Providers word this differently but it is nearly always the same
        # cause, and "AUTHENTICATIONFAILED" alone helps nobody.
        raise ImapError(
            f"Login failed for {creds.username}. If this mailbox has two-factor "
            f"authentication, use an app password rather than the account password. ({e})"
        )
    return conn


def _select(conn: imaplib.IMAP4, folder: str) -> int:
    """Select the folder and return its UIDVALIDITY.

    Read from SELECT's own untagged response rather than a follow-up STATUS:
    RFC 3501 specifically discourages STATUS against the mailbox you already
    have selected, and some servers answer it wrongly or not at all.
    """
    status, _ = conn.select(f'"{folder}"', readonly=True)
    if status != "OK":
        raise ImapError(f"Mailbox has no folder named {folder!r}")

    _, data = conn.response("UIDVALIDITY")
    if not data or not data[0]:
        return 0
    match = re.search(rb"\d+", data[0] if isinstance(data[0], bytes) else str(data[0]).encode())
    return int(match.group()) if match else 0


def test_connection(creds: Credentials) -> None:
    """Raises ImapError with a readable reason, or returns cleanly.

    Exists so an admin finds out a password is wrong while they are looking at
    the form, not in a log file at 07:10 the next morning.
    """
    conn = _connect(creds)
    try:
        _select(conn, creds.folder)
    finally:
        try:
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def fetch_messages(
    creds: Credentials, *, since_uid: int | None, uid_validity: int | None, lookback_days: int
) -> tuple[list[FetchedMessage], int]:
    """Return new messages and the folder's current UIDVALIDITY.

    `since_uid` is honoured only when `uid_validity` still matches the folder's.
    A server that renumbers a folder bumps UIDVALIDITY, at which point every
    stored UID means something different and continuing from one would silently
    skip real mail — so that case falls back to a date window instead.
    """
    conn = _connect(creds)
    try:
        current_validity = _select(conn, creds.folder)
        resume = since_uid is not None and uid_validity is not None and uid_validity == current_validity

        if resume:
            criteria = ("UID", f"{since_uid + 1}:*")
        else:
            if since_uid is not None:
                logger.warning(
                    "UIDVALIDITY changed for %s (%s -> %s) — falling back to a date window",
                    creds.username, uid_validity, current_validity,
                )
            since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
            criteria = ("SINCE", since)

        status, data = conn.uid("SEARCH", None, *criteria)
        if status != "OK":
            raise ImapError(f"Search failed on {creds.folder}")

        uids = [int(u) for u in (data[0] or b"").split()]
        # "UID n:*" always returns at least the newest message even when
        # nothing is newer than n, so drop anything already seen.
        if resume:
            uids = [u for u in uids if u > since_uid]

        # Newest first, then re-sorted ascending, so a mailbox over the cap
        # yields the most recent messages rather than the oldest ones.
        uids = sorted(sorted(uids, reverse=True)[:MAX_MESSAGES_PER_SYNC])

        messages: list[FetchedMessage] = []
        for uid in uids:
            status, payload = conn.uid("FETCH", str(uid), "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                logger.warning("Could not fetch UID %s from %s", uid, creds.username)
                continue
            msg = email.message_from_bytes(payload[0][1])
            sender, body = extract_sender_and_body(msg)
            messages.append(FetchedMessage(uid=uid, sender=sender, body=body))

        return messages, current_validity
    finally:
        try:
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
