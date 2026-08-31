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


def send_email(to: str, subject: str, body_text: str) -> bool:
    if not settings.SMTP_HOST:
        logger.info("SMTP not configured — skipping email to %s (%s)", to, subject)
        return False

    message = MIMEText(body_text)
    message["To"] = to
    message["From"] = settings.SMTP_FROM_EMAIL
    message["Subject"] = subject

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
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
