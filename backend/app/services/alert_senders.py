"""Recognising which job board an alert email came from.

Split out of the old Gmail-API message parser when mailboxes moved to IMAP.
Everything else in that module decoded Gmail's JSON payload format and died
with it; this part was never Gmail-specific at all — it matches a From header
against the configured job-alert domains, and works the same whatever fetched
the message.
"""

import re

from app.core.config import get_settings

settings = get_settings()

_EMAIL_RE = re.compile(r"([\w.+-]+@([\w-]+\.[\w.-]+))")


def load_domains(db) -> list[str]:
    """The allowlist, from the database.

    Read once per sync run and passed down, rather than queried per message:
    a mailbox batch is hundreds of messages and this list changes about once a
    month.
    """
    from app.models.alert_sender import AlertSender

    return [domain for (domain,) in db.query(AlertSender.domain).all()]


def detect_provider(sender: str, domains: list[str] | None = None) -> str | None:
    """Map a From header to a known job-alert provider slug (e.g. "linkedin"),
    or None if the sender's domain isn't on the allowlist.

    `domains` is the list loaded from the database. It falls back to the
    configured default only so the function stays usable without a session —
    production always passes the real list.

    Returning None is what stops an ordinary email in the operator's mailbox
    being sent to the extractor, so a receipt never costs an AI call or gets
    turned into a "job".
    """
    match = _EMAIL_RE.search(sender or "")
    if not match:
        return None

    address, domain = match.group(1).lower(), match.group(2).lower()

    # Checked before the domain match, because these *are* on allowed domains.
    # Boards use the same domain to tell an employer that someone applied to
    # their posting — mail that would otherwise cost an AI call and could be
    # read as a vacancy that does not exist.
    if address in settings.email_alert_sender_excludes_list:
        return None

    for known_domain in (settings.email_alert_sender_domains_list if domains is None else domains):
        # endswith guards the subdomain case (jobalerts.linkedin.com) without
        # matching a lookalike domain that merely ends in the same letters.
        if domain == known_domain or domain.endswith(f".{known_domain}"):
            return known_domain.split(".")[0]
    return None


# A manual forward puts the original headers in the body as a quoted block.
# Bounded and anchored to the start of a line so it matches a header block
# rather than the word "from" in a sentence.
_FORWARDED_FROM_RE = re.compile(r"(?im)^[>|\s]*from\s*:\s*(.{3,200})$")

# Only the top of the message is scanned: a forwarded header block sits above
# the quoted content, and reading the whole of a long digest would match every
# "From:" in a chain of replies.
_FORWARD_SCAN_CHARS = 4000


def detect_provider_anywhere(
    sender: str,
    domains: list[str] | None = None,
    *,
    hints: list[str] | None = None,
    body: str = "",
) -> str | None:
    """detect_provider, but able to see through a forward.

    Forwarding comes in two shapes and only one of them keeps working:

    Automatic forwarding — a rule at the source mailbox — resends the message
    with From untouched, so LinkedIn still looks like LinkedIn and the plain
    check matches. (It is why SPF famously breaks on forwarded mail.)

    A manual forward is a *new* message. From becomes the person who pressed
    the button, and the original is quoted in the body. Nothing about it is
    recognisable from From alone, so those alerts were silently skipped — the
    mailbox would report "read 12, recognised 0" and name the operator's own
    address as the unknown sender.

    So: From first, then the headers a forwarder may record the original in,
    then the quoted block. The domain still has to be on the allowlist and the
    exclude list still applies, so this widens *where* the sender is looked
    for, never which senders are accepted.
    """
    provider = detect_provider(sender, domains)
    if provider:
        return provider

    for hint in hints or []:
        provider = detect_provider(hint, domains)
        if provider:
            return provider

    for match in _FORWARDED_FROM_RE.finditer(body[:_FORWARD_SCAN_CHARS]):
        provider = detect_provider(match.group(1), domains)
        if provider:
            return provider

    return None
