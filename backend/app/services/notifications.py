"""Platform-sent email — the digest and admin alerts, distinct from Gmail
send in outreach.py (which sends *from the user's own inbox*, on their
behalf). This is generic SMTP so it isn't locked to one vendor's SDK.
"""

import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def open_smtp(timeout: float = 15.0) -> smtplib.SMTP:
    """Connected and authenticated, with the right kind of TLS for the port.

    Port 465 is implicit TLS: the server expects a TLS handshake as the very
    first thing on the socket. Opening it with plain smtplib.SMTP deadlocks —
    we wait for a 220 greeting that will never arrive in the clear, the server
    waits for a ClientHello — until the timeout fires. It surfaces as a
    connection timeout, which reads like a firewall or a wrong hostname and
    sends you looking in the wrong place entirely.

    Port 587 is the opposite order: greet in plain text, then STARTTLS.
    Which of the two is chosen follows the port unless SMTP_USE_SSL says
    otherwise.

    Shared with the integrations health check on purpose. A check that opens
    its connection differently from the code that sends the mail can go green
    against a server the digest cannot actually use.
    """
    if settings.smtp_implicit_tls:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)
        if settings.SMTP_USE_TLS:
            server.starttls()

    if settings.SMTP_USERNAME:
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
    return server


def send_email(to: str, subject: str, body_text: str, reply_to: str | None = None) -> bool:
    if not settings.SMTP_HOST:
        logger.info("SMTP not configured — skipping email to %s (%s)", to, subject)
        return False

    message = MIMEText(body_text)
    message["To"] = to
    message["From"] = settings.SMTP_FROM_EMAIL
    message["Subject"] = subject
    if reply_to:
        # Outreach relayed on a user's behalf: the envelope is ours (so SPF and
        # DKIM still pass) but a reply has to reach the person, not a noreply box.
        message["Reply-To"] = reply_to

    try:
        with open_smtp() as server:
            server.sendmail(settings.SMTP_FROM_EMAIL, [to], message.as_string())
        return True
    except (smtplib.SMTPException, OSError) as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return False


def alert_admin(subject: str, body_text: str) -> None:
    """Best-effort — the equivalent of Job Engine's dedicated error-alert
    workflow, generalized to email since there's no single shared Telegram
    chat for a multi-tenant product."""
    if not settings.ADMIN_ALERT_EMAIL:
        logger.warning("ADMIN_ALERT_EMAIL not set — alert dropped: %s", subject)
        return
    send_email(settings.ADMIN_ALERT_EMAIL, f"[HuntOps alert] {subject}", body_text)
