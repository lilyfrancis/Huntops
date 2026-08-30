import base64
import re

from app.core.config import get_settings

settings = get_settings()

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


def _decode_b64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except (ValueError, TypeError):
        return ""


def _walk_parts(payload: dict) -> str:
    body_data = payload.get("body", {}).get("data")
    mime_type = payload.get("mimeType", "")
    if mime_type.startswith("text/") and body_data:
        return _decode_b64url(body_data)

    parts = payload.get("parts", []) or []
    plain = next((p for p in parts if p.get("mimeType") == "text/plain"), None)
    html = next((p for p in parts if p.get("mimeType") == "text/html"), None)
    chosen = plain or html
    if chosen and chosen.get("body", {}).get("data"):
        return _decode_b64url(chosen["body"]["data"])

    for part in parts:
        text = _walk_parts(part)
        if text:
            return text
    return ""


def extract_sender_and_body(message: dict) -> tuple[str, str]:
    """Returns (raw From header value, decoded body text/html)."""
    headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
    sender = headers.get("from", "")
    body = _walk_parts(message.get("payload", {}))
    return sender, body


def detect_provider(sender: str) -> str | None:
    """Map a From header to a known job-alert provider slug (e.g. "linkedin"),
    or None if the sender's domain isn't in EMAIL_ALERT_SENDER_DOMAINS."""
    match = _EMAIL_RE.search(sender or "")
    if not match:
        return None
    domain = match.group(1).lower()
    for known_domain in settings.email_alert_sender_domains_list:
        if domain == known_domain or domain.endswith(f".{known_domain}"):
            return known_domain.split(".")[0]
    return None
