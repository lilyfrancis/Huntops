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

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


def detect_provider(sender: str) -> str | None:
    """Map a From header to a known job-alert provider slug (e.g. "linkedin"),
    or None if the sender's domain isn't in EMAIL_ALERT_SENDER_DOMAINS.

    Returning None is what stops an ordinary email in the operator's mailbox
    being sent to the extractor, so a receipt never costs an AI call or gets
    turned into a "job".
    """
    match = _EMAIL_RE.search(sender or "")
    if not match:
        return None
    domain = match.group(1).lower()
    for known_domain in settings.email_alert_sender_domains_list:
        # endswith guards the subdomain case (jobalerts.linkedin.com) without
        # matching a lookalike domain that merely ends in the same letters.
        if domain == known_domain or domain.endswith(f".{known_domain}"):
            return known_domain.split(".")[0]
    return None
